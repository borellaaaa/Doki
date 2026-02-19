"""
DOKI SAFETY GUARD — Sistema de Moderação v1.0
Autoregulação para conteúdos explícitos, crimes e conteúdo prejudicial.
"""
import re
from dataclasses import dataclass
from enum import Enum
from better_profanity import profanity

profanity.load_censor_words()


class ModerationResult(Enum):
    APPROVED = "approved"
    BLOCKED = "blocked"
    WARNING = "warning"


@dataclass
class ModerationResponse:
    result: ModerationResult
    reason: str = ""
    suggested_response: str = ""


# ──────────────────────────────────────────────
#  LISTAS DE TERMOS BLOQUEADOS (PT + EN)
# ──────────────────────────────────────────────

BLOCKED_PATTERNS = [
    # Crimes / atividades ilegais
    r"\b(como (fazer|fabricar|sintetizar|criar)|tutorial|passo a passo).{0,40}(bomb[ao]|explosiv|arma|veneno|droga|meth|crack|cocaína)\b",
    r"\b(hack(ear)?|invadir|crackear).{0,30}(sistema|servidor|conta|banco|rede)\b",
    r"\b(como (matar|assassinar|envenenar)|plano (para matar|de assassinato))\b",
    r"\b(pedofil|abuso (infantil|de menores)|criança.{0,20}(sexual|nua|pelada))\b",
    r"\b(terroris[mt]|ataque (terrorista|suicida)|explosão.{0,20}(shopping|escola|evento))\b",
    r"\b(tráfico (de pessoas|de drogas|humano)|escravidão moderna)\b",
    r"\b(fraude.{0,20}(cartão|banco|eleitor)|lavagem de dinheiro)\b",
    r"\b(ransomware|malware|keylogger|phishing|ddos attack)\b",

    # Conteúdo explícito sexual
    r"\b(pornografi[ac]|conteúdo (adulto|sexual|erótico|explícito))\b",
    r"\b(sexo (com|entre).{0,20}(menor|criança|animal))\b",
    r"\b(nude[sz]?|foto (nua?|pelad[ao])|conteúdo íntimo)\b",

    # Automutilação / suicídio (redireciona com cuidado)
    r"\b(como (me matar|suicidar|me machucar)|método.{0,20}suicídio|quero morrer)\b",
]

STUDY_BLOCK_PATTERNS = [
    # Tentativas de usar "é para estudar" como justificativa
    r"\b(para (estudar|pesquisa|trabalho).{0,30}(bomb[ao]|arma|veneno|explosiv))\b",
    r"\b(fins acadêmicos.{0,30}(hack|crackear|invadir))\b",
]

# Respostas padronizadas para cada categoria
RESPONSES = {
    "crime": (
        "🚫 Essa pergunta envolve atividades ilegais ou prejudiciais. "
        "A Doki foi criada para te ajudar a aprender — posso te ajudar com alguma matéria ou tópico de estudo?"
    ),
    "explicit": (
        "🚫 Esse tipo de conteúdo não está dentro do escopo da Doki. "
        "Estou aqui para te ajudar nos estudos! Tem alguma matéria que você quer explorar?"
    ),
    "self_harm": (
        "💙 Percebi que sua mensagem pode indicar que você está passando por um momento difícil. "
        "Se precisar de apoio, o CVV (Centro de Valorização da Vida) atende 24h pelo número 188 ou chat em cvv.org.br. "
        "Estou aqui se quiser conversar sobre outra coisa."
    ),
    "jailbreak": (
        "🛡️ Identificamos uma tentativa de contornar as diretrizes da Doki. "
        "Minhas regras existem para garantir um ambiente seguro de aprendizado."
    ),
}

JAILBREAK_PATTERNS = [
    r"\b(ignore (suas|as) (instruções|regras|diretrizes)|finja que (você é|não tem|pode))\b",
    r"\b(modo (desenvolvedor|sem restrições|sem filtro|desbloqueado))\b",
    r"\b(DAN|do anything now|jailbreak|bypass)\b",
    r"\b(aja como uma ia sem (regras|limites|restrições))\b",
    r"\b(sua (verdadeira|real) programação|seu (verdadeiro|real) eu)\b",
]


class ModerationService:
    """
    Serviço de moderação da Doki.
    Verifica cada mensagem antes de processar.
    """

    def __init__(self):
        self._blocked_re = [re.compile(p, re.IGNORECASE) for p in BLOCKED_PATTERNS]
        self._study_block_re = [re.compile(p, re.IGNORECASE) for p in STUDY_BLOCK_PATTERNS]
        self._jailbreak_re = [re.compile(p, re.IGNORECASE) for p in JAILBREAK_PATTERNS]

    def check(self, text: str) -> ModerationResponse:
        """Verifica o texto e retorna o resultado da moderação."""

        text_clean = text.strip().lower()

        # 1. Verificar jailbreak
        for pattern in self._jailbreak_re:
            if pattern.search(text_clean):
                return ModerationResponse(
                    result=ModerationResult.BLOCKED,
                    reason="jailbreak_attempt",
                    suggested_response=RESPONSES["jailbreak"],
                )

        # 2. Verificar automutilação (prioridade alta — resposta empática)
        if re.search(r"\b(como (me matar|suicidar|me machucar)|método.{0,20}suicídio|quero morrer)\b", text_clean, re.IGNORECASE):
            return ModerationResponse(
                result=ModerationResult.BLOCKED,
                reason="self_harm",
                suggested_response=RESPONSES["self_harm"],
            )

        # 3. Verificar padrões de crime/conteúdo explícito
        for pattern in self._blocked_re:
            if pattern.search(text_clean):
                reason = "explicit" if any(
                    w in text_clean for w in ["pornografi", "sexo", "nude", "explícito"]
                ) else "crime"
                return ModerationResponse(
                    result=ModerationResult.BLOCKED,
                    reason=reason,
                    suggested_response=RESPONSES[reason],
                )

        # 4. Verificar tentativa de usar "fins educacionais" para contornar
        for pattern in self._study_block_re:
            if pattern.search(text_clean):
                return ModerationResponse(
                    result=ModerationResult.BLOCKED,
                    reason="study_bypass_attempt",
                    suggested_response=RESPONSES["crime"],
                )

        # 5. Verificar comprimento máximo
        if len(text) > 4000:
            return ModerationResponse(
                result=ModerationResult.WARNING,
                reason="message_too_long",
                suggested_response="Sua mensagem é muito longa. Por favor, reduza para no máximo 4000 caracteres.",
            )

        return ModerationResponse(result=ModerationResult.APPROVED)


# Instância global
moderation_service = ModerationService()
