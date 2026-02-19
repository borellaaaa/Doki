"""
DOKI SUBJECT DETECTOR — Detecção automática de matéria/tópico v1.0
Classifica a pergunta do usuário na matéria correspondente.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class SubjectDetection:
    subject: str
    topic: Optional[str]
    confidence: float      # 0.0 a 1.0
    keywords_found: list[str]


# ──────────────────────────────────────────────
#  TAXONOMIA DE MATÉRIAS
# ──────────────────────────────────────────────

SUBJECT_TAXONOMY: dict[str, dict] = {
    "matematica": {
        "display": "Matemática",
        "icon": "📐",
        "keywords": [
            "equação", "função", "derivada", "integral", "limite", "matriz", "vetor",
            "geometria", "trigonometria", "logaritmo", "polinômio", "probabilidade",
            "estatística", "álgebra", "cálculo", "número", "fração", "porcentagem",
            "raiz", "potência", "progressão", "combinatória", "permutação",
        ],
        "topics": {
            "calculo": ["derivada", "integral", "limite", "cálculo diferencial", "cálculo integral"],
            "algebra": ["equação", "sistema linear", "matriz", "determinante", "vetor"],
            "geometria": ["triângulo", "círculo", "polígono", "área", "volume", "perímetro"],
            "estatistica": ["média", "mediana", "moda", "desvio padrão", "distribuição"],
        },
    },
    "fisica": {
        "display": "Física",
        "icon": "⚛️",
        "keywords": [
            "força", "energia", "velocidade", "aceleração", "massa", "gravitação",
            "eletricidade", "magnetismo", "onda", "luz", "calor", "termodinâmica",
            "mecânica", "óptica", "relatividade", "quantum", "partícula", "pressão",
            "trabalho", "potência", "campo elétrico", "campo magnético", "circuito",
        ],
        "topics": {
            "mecanica": ["força", "velocidade", "aceleração", "trabalho", "energia cinética"],
            "eletromagnetismo": ["eletricidade", "magnetismo", "campo elétrico", "circuito"],
            "termodinamica": ["calor", "temperatura", "entropia", "termodinâmica"],
            "optica": ["luz", "refração", "reflexão", "lente", "espelho"],
        },
    },
    "quimica": {
        "display": "Química",
        "icon": "🧪",
        "keywords": [
            "átomo", "molécula", "reação", "elemento", "tabela periódica", "ligação",
            "ácido", "base", "sal", "óxido", "pH", "mol", "solução", "concentração",
            "oxidação", "redução", "orgânica", "inorgânica", "isômero", "polímero",
            "estequiometria", "equilíbrio químico", "cinética",
        ],
        "topics": {
            "organica": ["carbono", "hidrocarboneto", "álcool", "ácido orgânico", "isômero"],
            "inorganica": ["tabela periódica", "ligação iônica", "ligação covalente"],
            "fisicoquimica": ["equilíbrio", "cinética", "termodinâmica química", "eletroquímica"],
        },
    },
    "biologia": {
        "display": "Biologia",
        "icon": "🧬",
        "keywords": [
            "célula", "DNA", "RNA", "proteína", "gene", "cromossomo", "evolução",
            "ecossistema", "fotossíntese", "respiração celular", "mitose", "meiose",
            "vírus", "bactéria", "fungo", "animal", "planta", "ecologia", "genética",
            "metabolismo", "enzima", "hormônio", "tecido", "órgão", "sistema",
        ],
        "topics": {
            "genetica": ["DNA", "gene", "hereditariedade", "mutação", "cromossomo"],
            "ecologia": ["ecossistema", "cadeia alimentar", "bioma", "população"],
            "citologia": ["célula", "membrana", "mitocôndria", "núcleo", "organela"],
            "evolucao": ["Darwin", "seleção natural", "especiação", "fóssil"],
        },
    },
    "historia": {
        "display": "História",
        "icon": "📜",
        "keywords": [
            "guerra", "revolução", "império", "república", "colônia", "independência",
            "ditadura", "democracia", "feudalismo", "capitalismo", "socialismo",
            "brasil", "europa", "antiguidade", "medievalidade", "renascimento",
            "iluminismo", "industrialização", "segunda guerra", "primeira guerra",
        ],
        "topics": {
            "brasil": ["colônia", "império", "república", "ditadura militar", "redemocratização"],
            "geral": ["antiguidade", "idade média", "idade moderna", "idade contemporânea"],
            "guerras": ["primeira guerra", "segunda guerra", "guerra fria", "guerra civil"],
        },
    },
    "geografia": {
        "display": "Geografia",
        "icon": "🌍",
        "keywords": [
            "clima", "relevo", "hidrografia", "bioma", "urbanização", "população",
            "continente", "país", "capital", "latitude", "longitude", "mapa",
            "geopolítica", "globalização", "desenvolvimento", "IDH", "pib",
        ],
    },
    "portugues": {
        "display": "Português",
        "icon": "📝",
        "keywords": [
            "verbo", "substantivo", "adjetivo", "advérbio", "preposição", "conjunção",
            "oração", "sujeito", "predicado", "crase", "acento", "ortografia",
            "redação", "dissertação", "narração", "coesão", "coerência", "texto",
            "literatura", "poesia", "romance", "conto", "interpretação",
        ],
        "topics": {
            "gramatica": ["verbo", "substantivo", "crase", "concordância", "regência"],
            "literatura": ["romantismo", "realismo", "modernismo", "poesia", "prosa"],
            "redacao": ["dissertação", "argumentação", "coesão", "coerência"],
        },
    },
    "ingles": {
        "display": "Inglês",
        "icon": "🇺🇸",
        "keywords": [
            "verb", "tense", "grammar", "vocabulary", "present", "past", "future",
            "reading", "writing", "speaking", "listening", "phrasal verb",
            "conditional", "modal", "passive voice", "reported speech",
        ],
    },
    "programacao": {
        "display": "Programação",
        "icon": "💻",
        "keywords": [
            "código", "função", "variável", "loop", "array", "objeto", "classe",
            "python", "javascript", "java", "c++", "sql", "html", "css", "react",
            "algoritmo", "estrutura de dados", "banco de dados", "api", "recursão",
            "debug", "compilador", "framework", "biblioteca",
        ],
        "topics": {
            "python": ["python", "django", "flask", "pandas", "numpy"],
            "web": ["html", "css", "javascript", "react", "api rest"],
            "estrutura_dados": ["array", "lista", "pilha", "fila", "árvore", "grafo"],
            "banco_dados": ["sql", "mysql", "postgresql", "nosql", "mongodb"],
        },
    },
    "filosofia": {
        "display": "Filosofia",
        "icon": "🏛️",
        "keywords": [
            "ética", "moral", "epistemologia", "ontologia", "metafísica", "lógica",
            "sócrates", "platão", "aristóteles", "kant", "nietzsche", "descartes",
            "existencialismo", "empirismo", "racionalismo", "fenomenologia",
        ],
    },
    "matematica_financeira": {
        "display": "Matemática Financeira",
        "icon": "💰",
        "keywords": [
            "juros", "desconto", "amortização", "investimento", "rentabilidade",
            "taxa", "capitalização", "anuidade", "VP", "VPL", "TIR", "payback",
        ],
    },
}


class SubjectDetectorService:
    """Detecta automaticamente a matéria de uma pergunta."""

    def detect(self, text: str) -> SubjectDetection:
        text_lower = text.lower()
        scores: dict[str, float] = {}
        keywords_found: dict[str, list[str]] = {}

        for subject_key, data in SUBJECT_TAXONOMY.items():
            found = []
            for keyword in data["keywords"]:
                if keyword in text_lower:
                    found.append(keyword)

            if found:
                # Score = % de keywords encontradas (com peso para matches múltiplos)
                score = min(len(found) / max(len(data["keywords"]) * 0.1, 1), 1.0)
                scores[subject_key] = score
                keywords_found[subject_key] = found

        if not scores:
            return SubjectDetection(
                subject="geral",
                topic=None,
                confidence=0.0,
                keywords_found=[],
            )

        best_subject = max(scores, key=scores.__getitem__)
        confidence = min(scores[best_subject] * 2, 0.99)  # normaliza

        # Detectar tópico específico
        topic = self._detect_topic(best_subject, text_lower)

        return SubjectDetection(
            subject=best_subject,
            topic=topic,
            confidence=confidence,
            keywords_found=keywords_found.get(best_subject, []),
        )

    def _detect_topic(self, subject: str, text_lower: str) -> Optional[str]:
        data = SUBJECT_TAXONOMY.get(subject, {})
        topics = data.get("topics", {})

        for topic_key, topic_keywords in topics.items():
            if any(kw in text_lower for kw in topic_keywords):
                return topic_key

        return None

    def get_display_name(self, subject_key: str) -> str:
        return SUBJECT_TAXONOMY.get(subject_key, {}).get("display", subject_key.capitalize())

    def get_icon(self, subject_key: str) -> str:
        return SUBJECT_TAXONOMY.get(subject_key, {}).get("icon", "📚")


subject_detector = SubjectDetectorService()
