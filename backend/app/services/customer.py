"""Customer services: CRUD on the AR sub-ledger contacts.

Mirrors the existing ``app.services.account`` pattern closely. Search-
by-query and deactivate/reactivate are first-class because every
real-world AR workflow needs them.

Hard deletion is intentionally not exposed at the service layer.
Customers with history should never be removed; future phases will
add a database trigger (in migration 0003, once invoices exist) that
rejects DELETE on any customer with an invoice. Today the service
layer refuses DELETE at the API level; the trigger provides
belt-and-braces coverage once invoices ship.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.audit import AuditAction
from app.models.contact import Customer
from app.schemas.customer import CustomerCreate, CustomerUpdate
from app.services.audit import record_audit


def _validate_account_for_income(session: Session, account_id: int) -> None:
    """Default-income account must exist and be of type 'income'."""
    account = session.get(Account, account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"default_income_account_id {account_id} not found",
        )
    if account.type.value != "income":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"default_income_account_id {account_id} must be an income "
                f"account, got {account.type.value!r}"
            ),
        )


def list_customers(
    session: Session,
    *,
    include_inactive: bool = False,
    query: str | None = None,
) -> list[Customer]:
    stmt = select(Customer).order_by(Customer.name)
    if not include_inactive:
        stmt = stmt.where(Customer.is_active.is_(True))
    if query:
        like = f"%{query}%"
        stmt = stmt.where(
            or_(
                Customer.name.ilike(like),
                Customer.code.ilike(like),
                Customer.company.ilike(like),
                Customer.email.ilike(like),
            )
        )
    return list(session.execute(stmt).scalars().all())


def get_customer(session: Session, customer_id: int) -> Customer:
    customer = session.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"customer {customer_id} not found",
        )
    return customer


def create_customer(
    session: Session,
    payload: CustomerCreate,
    *,
    actor: str | None = None,
) -> Customer:
    if payload.default_income_account_id is not None:
        _validate_account_for_income(session, payload.default_income_account_id)

    data = payload.model_dump()
    customer = Customer(**data)
    session.add(customer)
    try:
        session.flush()
    except IntegrityError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"customer code {payload.code!r} already exists",
        ) from e

    record_audit(
        session,
        action=AuditAction.CREATE,
        entity_type="customer",
        entity_id=customer.id,
        after=data,
        actor=actor,
    )
    return customer


def update_customer(
    session: Session,
    customer_id: int,
    payload: CustomerUpdate,
    *,
    actor: str | None = None,
) -> Customer:
    customer = get_customer(session, customer_id)
    updates = payload.model_dump(exclude_unset=True)

    if (
        "default_income_account_id" in updates
        and updates["default_income_account_id"] is not None
    ):
        _validate_account_for_income(session, updates["default_income_account_id"])

    before = {key: getattr(customer, key) for key in updates}
    for key, value in updates.items():
        setattr(customer, key, value)
    session.flush()
    record_audit(
        session,
        action=AuditAction.UPDATE,
        entity_type="customer",
        entity_id=customer.id,
        before=before,
        after=updates,
        actor=actor,
    )
    return customer


def deactivate_customer(
    session: Session,
    customer_id: int,
    *,
    actor: str | None = None,
) -> Customer:
    customer = get_customer(session, customer_id)
    if not customer.is_active:
        return customer
    customer.is_active = False
    session.flush()
    record_audit(
        session,
        action=AuditAction.DEACTIVATE,
        entity_type="customer",
        entity_id=customer.id,
        actor=actor,
    )
    return customer


def reactivate_customer(
    session: Session,
    customer_id: int,
    *,
    actor: str | None = None,
) -> Customer:
    customer = get_customer(session, customer_id)
    if customer.is_active:
        return customer
    customer.is_active = True
    session.flush()
    record_audit(
        session,
        action=AuditAction.REACTIVATE,
        entity_type="customer",
        entity_id=customer.id,
        actor=actor,
    )
    return customer
