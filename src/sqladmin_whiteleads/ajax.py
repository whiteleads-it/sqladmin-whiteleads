from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import String, cast, inspect, or_, select

from sqladmin_whiteleads.helpers import get_object_identifier, get_primary_keys

if TYPE_CHECKING:
    from sqladmin_whiteleads.models import ModelView


DEFAULT_PAGE_SIZE = 100


class QueryAjaxModelLoader:
    def __init__(
        self,
        name: str,
        model: type,
        model_admin: "ModelView",
        **options: Any,
    ):
        self.name = name
        self.model = model
        self.model_admin = model_admin
        self.fields = options.get("fields", {})
        self.order_by = options.get("order_by")
        self.limit = options.get("limit", DEFAULT_PAGE_SIZE)
        self.condition = options.get("condition", None)
        pks = get_primary_keys(self.model)
        self.pk = pks[0] if len(pks) == 1 else None

        if not self.fields:
            raise ValueError(
                "AJAX loading requires `fields` to be specified for "
                f"{self.model}.{self.name}"
            )
        self._cached_fields = self._process_fields()

    def _process_fields(self) -> list:
        remote_fields = []

        for field in self.fields:
            if isinstance(field, str):
                attr = getattr(self.model, field, None)

                if not attr:
                    raise ValueError(f"{self.model}.{field} does not exist.")
                remote_fields.append(attr)
            else:
                remote_fields.append(field)

        return remote_fields

    def format(self, model: type) -> dict[str, Any]:
        if not model:
            return {}

        return {"id": str(get_object_identifier(model)), "text": str(model)}

    async def get_list(self, term: str) -> list[Any]:
        stmt = select(self.model)
        if term is not None:
            filters = [
                cast(field, String).ilike(f"%{term}%")
                for field in self._cached_fields
            ]
            stmt = stmt.filter(or_(*filters))
        if hasattr(self, 'condition') and self.condition is not None:
            condition = self.condition if isinstance(self.condition, list) else [self.condition]
            for cond in condition:
                stmt = stmt.where(cond)
        if hasattr(self, 'order_by'):
            order_by = self.order_by if isinstance(self.order_by, list) else [self.order_by]
            for o in order_by:
                stmt = stmt.order_by(o)
        if hasattr(self, 'limit'):
            stmt = stmt.limit(self.limit)
        result = await self.model_admin._run_query(stmt)
        return result


def create_ajax_loader(
    *,
    model_admin: "ModelView",
    name: str,
    options: dict,
) -> QueryAjaxModelLoader:
    mapper = inspect(model_admin.model)
    try:
        attr = mapper.relationships[name]
    except KeyError:
        raise ValueError(f"{model_admin.model}.{name} is not a relation.")
    remote_model = attr.mapper.class_
    return QueryAjaxModelLoader(name, remote_model, model_admin, **options)
