from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.auth import verify_token
from src.db.routing_repository import RoutingRepository
from src.routing.condition_evaluator import ConditionEvaluator
from src.routing.engine import RoutingEngine

router = APIRouter(prefix="/api/routing-rules", tags=["routing"])

repo = RoutingRepository()


class ConditionSchema(BaseModel):
    field: str
    operator: str
    value: str | int | float | bool | list


class ActionSchema(BaseModel):
    type: str
    params: dict = {}


class RuleCreateRequest(BaseModel):
    name: str
    priority: int = 100
    enabled: bool = True
    conditions: list[ConditionSchema]
    condition_logic: str = "AND"
    actions: list[ActionSchema]
    stop_processing: bool = False
    created_by: str | None = None


class RuleUpdateRequest(BaseModel):
    name: str | None = None
    priority: int | None = None
    enabled: bool | None = None
    conditions: list[ConditionSchema] | None = None
    condition_logic: str | None = None
    actions: list[ActionSchema] | None = None
    stop_processing: bool | None = None


class DryRunRequest(BaseModel):
    """Contesto email per simulazione dry-run."""
    security: dict = {}
    country: dict = {}
    content: dict = {}
    email: dict = {}


@router.get("")
def list_rules(_user: str = Depends(verify_token)):
    """GET lista di tutte le regole di routing."""
    rules = repo.get_all_rules()
    return {"rules": rules, "count": len(rules)}


@router.get("/{rule_id}")
def get_rule(rule_id: int, _user: str = Depends(verify_token)):
    """GET singola regola per ID."""
    rule = repo.get_rule_by_id(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return rule


@router.post("", status_code=201)
def create_rule(request: RuleCreateRequest, _user: str = Depends(verify_token)):
    """POST crea una nuova regola."""
    data = request.model_dump(exclude_none=True)
    data["conditions"] = [c.model_dump() for c in request.conditions]
    data["actions"] = [a.model_dump() for a in request.actions]

    rule_id = repo.create_rule(data)
    rule = repo.get_rule_by_id(rule_id)
    return rule


@router.put("/{rule_id}")
def update_rule(rule_id: int, request: RuleUpdateRequest, _user: str = Depends(verify_token)):
    """PUT modifica una regola esistente."""
    existing = repo.get_rule_by_id(rule_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")

    data = request.model_dump(exclude_none=True)
    if "conditions" in data and request.conditions:
        data["conditions"] = [c.model_dump() for c in request.conditions]
    if "actions" in data and request.actions:
        data["actions"] = [a.model_dump() for a in request.actions]

    repo.update_rule(rule_id, data)
    return repo.get_rule_by_id(rule_id)


@router.delete("/{rule_id}")
def delete_rule(rule_id: int, _user: str = Depends(verify_token)):
    """DELETE elimina una regola."""
    existing = repo.get_rule_by_id(rule_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")

    repo.delete_rule(rule_id)
    return {"deleted": True, "rule_id": rule_id}


@router.post("/dry-run")
def dry_run(request: DryRunRequest, _user: str = Depends(verify_token)):
    """Simula la valutazione delle regole su un contesto email senza eseguire azioni."""
    email_context = request.model_dump()

    engine = RoutingEngine()
    actions = engine.evaluate(email_context)

    return {
        "context": email_context,
        "matched_actions": actions,
        "actions_count": len(actions),
        "would_block": any(a["action_type"] == "block" for a in actions),
        "would_quarantine": any(a["action_type"] == "quarantine" for a in actions),
    }
