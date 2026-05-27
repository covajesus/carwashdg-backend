from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    branches,
    brands,
    cash_closure,
    clients,
    car_types,
    configurations,
    customers,
    expenses,
    collections,
    health,
    raffles,
    reports,
    roles,
    services,
    settings,
    sliders,
    statuses,
    ticket_lines,
    tickets,
    users,
    washer_pay,
    washer_daily_groups,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(health.router)
api_router.include_router(branches.router)
api_router.include_router(car_types.router)
api_router.include_router(statuses.router)
api_router.include_router(raffles.router)
api_router.include_router(sliders.router)
api_router.include_router(brands.router)
api_router.include_router(clients.router)
api_router.include_router(settings.router)
api_router.include_router(configurations.router)
api_router.include_router(customers.router)
api_router.include_router(cash_closure.router)
api_router.include_router(expenses.router)
api_router.include_router(collections.router)
api_router.include_router(reports.router)
api_router.include_router(services.router)
api_router.include_router(roles.router)
api_router.include_router(tickets.router)
api_router.include_router(ticket_lines.router)
api_router.include_router(washer_pay.router)
api_router.include_router(washer_daily_groups.router)
