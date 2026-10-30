"""Base de conocimiento: carga de documentos markdown y recuperación léxica (BM25).

Decisión: el corpus del CV es pequeño; su costo se verifica con el uso del modelo,
así que el modo por defecto es `full` (todo el contexto, sin riesgo de que la
recuperación omita un dato). El modo `retrieval` existe para demostrar cómo
escalaría si la base creciera (p. ej. agregar READMEs de repos, publicaciones) y
se compara contra `full` en la suite de evaluación.
"""
from __future__ import annotations

import math
import hashlib
import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from html import escape
from pathlib import Path

import yaml


@dataclass
class Chunk:
    doc_id: str
    title: str
    heading: str
    text: str
    tags: list[str]

    @property
    def ref(self) -> str:
        return f"{self.doc_id}#{_slug(self.heading)}" if self.heading else self.doc_id


@dataclass
class Document:
    doc_id: str
    title: str
    tags: list[str]
    body: str


STOPWORDS = set(
    """a al algo como con cual cuales de del el ella ellas en era es esa ese eso esta este
    esto fue ha han hay la las le les lo los mas me mi mis muy no o para pero por que se sin
    sobre su sus te tiene tu un una uno y ya the of and to in is are was what which who how his
    he does did do for on with about tell me cuéntame cuentame dime sabes carlos ignacio alonso reyes donde""".split()
)


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def tokenize(text: str) -> list[str]:
    text = _strip_accents(text.lower())
    toks = re.findall(r"[a-z0-9][a-z0-9+#.\-]*", text)
    out = []
    for t in toks:
        t = t.strip(".-")
        if len(t) < 2 or t in STOPWORDS:
            continue
        # stemming muy ligero para español/inglés
        for suf in ("aciones", "acion", "mente", "es", "s"):
            if len(t) > 5 and t.endswith(suf):
                t = t[: -len(suf)]
                break
        out.append(t)
    return out


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _strip_accents(s.lower())).strip("-")


def load_documents(knowledge_dir: Path) -> list[Document]:
    docs = []
    for path in sorted(knowledge_dir.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        meta, body = {}, raw
        if raw.startswith("---"):
            _, fm, body = raw.split("---", 2)
            meta = yaml.safe_load(fm) or {}
        docs.append(
            Document(
                doc_id=meta.get("id", path.stem),
                title=meta.get("title", path.stem),
                tags=list(meta.get("tags", [])),
                body=body.strip(),
            )
        )
    if not docs:
        raise RuntimeError(f"No hay documentos de conocimiento en {knowledge_dir}")
    return docs


def chunk_documents(docs: list[Document]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for d in docs:
        parts = re.split(r"(?m)^(#{1,2} .+)$", d.body)
        heading, buf = "", ""
        for p in parts:
            if re.match(r"^#{1,2} ", p):
                if buf.strip():
                    chunks.append(Chunk(d.doc_id, d.title, heading, buf.strip(), d.tags))
                heading, buf = p.lstrip("# ").strip(), p + "\n"
            else:
                buf += p
        if buf.strip():
            chunks.append(Chunk(d.doc_id, d.title, heading, buf.strip(), d.tags))
    return chunks


class BM25:
    def __init__(self, chunks: list[Chunk], k1: float = 1.4, b: float = 0.75):
        self.chunks = chunks
        self.k1, self.b = k1, b
        # Tags/título (curados a mano) suman al documento; el encabezado de sección pesa triple.
        self.docs_toks = [
            tokenize(c.text) + tokenize(" ".join(c.tags) + " " + c.title) + 3 * tokenize(c.heading)
            for c in chunks
        ]
        self.tf = [Counter(t) for t in self.docs_toks]
        self.avgdl = sum(len(t) for t in self.docs_toks) / max(len(self.docs_toks), 1)
        df = Counter(tok for toks in self.docs_toks for tok in set(toks))
        n = len(chunks)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, k: int = 3) -> list[tuple[Chunk, float]]:
        q = tokenize(query)
        scores = []
        for i, tf in enumerate(self.tf):
            dl = len(self.docs_toks[i])
            s = 0.0
            for t in q:
                if t in tf:
                    f = tf[t]
                    s += self.idf.get(t, 0) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            scores.append((self.chunks[i], s))
        scores.sort(key=lambda x: x[1], reverse=True)
        return [x for x in scores[:k] if x[1] > 0]


class KnowledgeBase:
    def __init__(self, knowledge_dir: Path):
        self.docs = load_documents(knowledge_dir)
        # Identifica exactamente el corpus usado en una demo o evaluación; no es
        # una certificación de veracidad de los datos aportados por el candidato.
        canonical = [{"id": d.doc_id, "title": d.title, "tags": d.tags, "body": d.body} for d in self.docs]
        self.revision = hashlib.sha256(json.dumps(canonical, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]
        self.chunks = chunk_documents(self.docs)
        self.index = BM25(self.chunks)
        # El perfil siempre va en contexto: ancla identidad y contacto.
        self.anchor = next((d for d in self.docs if d.doc_id == "perfil"), self.docs[0])

    def full_context(self) -> str:
        return "\n\n".join(f'<documento id="{escape(d.doc_id)}" titulo="{escape(d.title)}">\n{escape(d.body)}\n</documento>' for d in self.docs)

    def retrieved_context(self, query: str, k: int) -> tuple[str, list[str]]:
        hits = self.index.search(query, k=k)
        parts = [f'<documento id="{escape(self.anchor.doc_id)}" titulo="{escape(self.anchor.title)}">\n{escape(self.anchor.body)}\n</documento>']
        refs = [self.anchor.doc_id]
        for c, _ in hits:
            if c.doc_id == self.anchor.doc_id:
                continue
            parts.append(f'<fragmento id="{escape(c.doc_id)}" ref="{escape(c.ref)}" titulo="{escape(c.title)}">\n{escape(c.text)}\n</fragmento>')
            refs.append(c.ref)
        return "\n\n".join(parts), refs
