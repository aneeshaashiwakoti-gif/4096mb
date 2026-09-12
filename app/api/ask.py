"""Repository-grounded developer assistant endpoint."""

from typing import List
from fastapi import APIRouter, Depends
from app.llm.base import LLMProvider
from app.llm.factory import get_llm_provider
from app.models.common import Claim, CodeCitation, ConfidenceLevel
from app.models.requests import AskRequest, FixProposalRequest
from app.models.responses import AskResponse
from app.prompts.ask_prompt import ASK_SYSTEM_PROMPT, format_ask_user_prompt
from app.reasoning.claim_verifier import ClaimVerifier
from app.reasoning.fix_engine import FixEngine
from app.reasoning.intent import IntentAnalyzer
from app.utils.logging import logger
from app.indexing.service import project_index

router = APIRouter()


@router.post("/ask", response_model=AskResponse)
async def ask_assistant(
    payload: AskRequest,
    llm: LLMProvider = Depends(get_llm_provider),
) -> AskResponse:
    """Answer developer questions strictly grounded in supplied repository evidence."""
    logger.info(f"Received developer inquiry: '{payload.question}'")

    # The original contract still accepts caller-supplied evidence.  When the
    # local agent has an index, enrich an empty request with retrieved code so
    # the LLM remains a reasoning layer rather than a filesystem layer.
    if not payload.evidence and project_index.connected:
        payload.evidence = project_index.evidence_for_query(payload.question)
        if payload.evidence:
            payload.project_id = project_index.root.name

    all_evidence = list(payload.evidence)
    if payload.impact_context and payload.impact_context.evidence:
        all_evidence.extend(payload.impact_context.evidence)

    # 1. Query LLM
    prompt = format_ask_user_prompt(payload)
    raw_response = await llm.generate_structured(
        prompt=prompt,
        system_prompt=ASK_SYSTEM_PROMPT,
    )

    # 2. Extract and verify claims and citations
    raw_claims = raw_response.get("claims", [])
    claims: List[Claim] = []
    for c in raw_claims:
        if isinstance(c, dict):
            citations = [
                CodeCitation(**cit) if isinstance(cit, dict) else cit
                for cit in c.get("citations", [])
            ]
            claims.append(
                Claim(
                    statement=c.get("statement", ""),
                    category=c.get("category", "INFERENCE"),
                    citations=citations,
                )
            )

    ClaimVerifier.verify_claims(claims, all_evidence)

    # Citations at top level
    raw_citations = raw_response.get("citations", [])
    citations: List[CodeCitation] = []
    for cit in raw_citations:
        citation_obj = CodeCitation(**cit) if isinstance(cit, dict) else cit
        ClaimVerifier.verify_citation(citation_obj, all_evidence)
        citations.append(citation_obj)

    # 3. Check if user asked for a fix
    fix_proposal = None
    if IntentAnalyzer.is_fix_request(payload.question) and payload.impact_context:
        fix_req = FixProposalRequest(
            instruction=payload.question,
            constraints=payload.constraints,
            impact_analysis=payload.impact_context,
            evidence=all_evidence,
        )
        # Generate proposal safely
        from app.prompts.fix_prompt import FIX_SYSTEM_PROMPT, format_fix_user_prompt
        fix_prompt = format_fix_user_prompt(fix_req)
        raw_fix = await llm.generate_structured(prompt=fix_prompt, system_prompt=FIX_SYSTEM_PROMPT)
        fix_proposal = FixEngine.evaluate_and_build_proposal(fix_req, raw_fix)

    # 4. Confidence evaluation
    total_cit = len(citations) + sum(len(c.citations) for c in claims)
    ver_cit = sum(1 for c in citations if c.verified) + sum(1 for c in claims for cit in c.citations if cit.verified)

    if total_cit > 0 and (ver_cit / total_cit) >= 0.8:
        confidence = ConfidenceLevel.HIGH
    elif not all_evidence:
        confidence = ConfidenceLevel.LOW
    else:
        confidence = ConfidenceLevel.MEDIUM

    return AskResponse(
        answer=raw_response.get("answer", "No answer could be determined from the supplied evidence."),
        claims=claims,
        citations=citations,
        recommended_actions=raw_response.get("recommended_actions", []),
        confidence=confidence,
        uncertainties=raw_response.get("uncertainties", []),
        fix_proposal=fix_proposal,
    )
