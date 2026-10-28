"""Workspaces, departments, locations, vendors and products."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.server.fastmcp.exceptions import ToolError
from pydantic import Field

from ..client import clean, get_client, quote_query
from ._common import CustomFields, Page, PerPage, Result
from ._registry import toolset

ts = toolset("organisation", "Workspaces, departments, locations, vendors and products")

# --- Workspaces ----------------------------------------------------------------------------------


@ts.tool("List workspaces")
async def list_all_workspaces(page: Page = 1, per_page: PerPage = 30) -> Result:
    """List workspaces (use their IDs as workspace_id elsewhere)."""
    return await get_client().list("/workspaces", "workspaces", page=page, per_page=per_page)


@ts.tool("Get workspace")
async def get_workspace(workspace_id: Annotated[int, Field(description="Workspace ID")]) -> Result:
    """Get a workspace by ID."""
    return await get_client().get(f"/workspaces/{workspace_id}")


# --- Departments ---------------------------------------------------------------------------------

DepartmentId = Annotated[int, Field(description="Department ID")]


@ts.tool("List department fields")
async def list_department_fields() -> Result:
    """List department fields, including custom fields."""
    return await get_client().get("/department_fields")


@ts.tool("List departments")
async def list_departments(
    page: Page = 1,
    per_page: PerPage = 30,
    query: Annotated[
        str | None,
        Field(description="Freshservice query, e.g. \"name:'Finance'\"; outer quotes added for you"),
    ] = None,
) -> Result:
    """List departments, optionally filtered by query."""
    params = {"query": quote_query(query) if query else None}
    return await get_client().list("/departments", "departments", page=page, per_page=per_page, params=params)


@ts.tool("Get department")
async def get_department(department_id: DepartmentId) -> Result:
    """Get a department by ID."""
    return await get_client().get(f"/departments/{department_id}")


@ts.tool("Create department", "create")
async def create_department(
    name: Annotated[str, Field(min_length=1, description="Department name")],
    description: Annotated[str | None, Field()] = None,
    head_user_id: Annotated[int | None, Field(description="Department head user ID")] = None,
    prime_user_id: Annotated[int | None, Field(description="Primary contact user ID")] = None,
    domains: Annotated[list[str] | None, Field(description="Email domains mapped to the department")] = None,
    custom_fields: CustomFields = None,
) -> Result:
    """Create a department."""
    payload = clean(
        {
            "name": name,
            "description": description,
            "head_user_id": head_user_id,
            "prime_user_id": prime_user_id,
            "domains": domains,
            "custom_fields": custom_fields,
        }
    )
    return await get_client().post("/departments", payload)


@ts.tool("Update department", "update")
async def update_department(
    department_id: DepartmentId,
    department_fields: Annotated[
        dict[str, Any],
        Field(description="name, description, head_user_id, prime_user_id, domains, custom_fields"),
    ],
) -> Result:
    """Update a department."""
    if not department_fields:
        raise ToolError("No fields provided for update")
    return await get_client().put(f"/departments/{department_id}", clean(department_fields))


@ts.tool("Delete department", "delete")
async def delete_department(department_id: DepartmentId) -> Result:
    """Delete a department."""
    return await get_client().delete(f"/departments/{department_id}")


# --- Locations -----------------------------------------------------------------------------------

LocationId = Annotated[int, Field(description="Location ID")]


@ts.tool("List locations")
async def list_locations(
    page: Page = 1,
    per_page: PerPage = 30,
    query: Annotated[
        str | None, Field(description="Filter by name only, e.g. \"name:'Sydney HQ'\"; outer quotes added")
    ] = None,
) -> Result:
    """List locations, optionally filtered by query."""
    params = {"query": quote_query(query) if query else None}
    return await get_client().list("/locations", "locations", page=page, per_page=per_page, params=params)


@ts.tool("Get location")
async def get_location(location_id: LocationId) -> Result:
    """Get a location by ID."""
    return await get_client().get(f"/locations/{location_id}")


@ts.tool("Create location", "create")
async def create_location(
    name: Annotated[str, Field(min_length=1, description="Location name")],
    parent_location_id: Annotated[int | None, Field()] = None,
    primary_contact_id: Annotated[int | None, Field()] = None,
    address: Annotated[
        dict[str, str] | None, Field(description="line1, line2, city, state, country, zipcode")
    ] = None,
) -> Result:
    """Create a location."""
    payload = clean(
        {
            "name": name,
            "parent_location_id": parent_location_id,
            "primary_contact_id": primary_contact_id,
            "address": address,
        }
    )
    return await get_client().post("/locations", payload)


@ts.tool("Update location", "update")
async def update_location(
    location_id: LocationId,
    location_fields: Annotated[
        dict[str, Any], Field(description="name, parent_location_id, primary_contact_id, address")
    ],
) -> Result:
    """Update a location."""
    if not location_fields:
        raise ToolError("No fields provided for update")
    return await get_client().put(f"/locations/{location_id}", clean(location_fields))


@ts.tool("Delete location", "delete")
async def delete_location(location_id: LocationId) -> Result:
    """Delete a location."""
    return await get_client().delete(f"/locations/{location_id}")


# --- Vendors -------------------------------------------------------------------------------------


@ts.tool("List vendors")
async def list_vendors(page: Page = 1, per_page: PerPage = 30) -> Result:
    """List vendors."""
    return await get_client().list("/vendors", "vendors", page=page, per_page=per_page)


@ts.tool("Get vendor")
async def get_vendor(vendor_id: Annotated[int, Field(description="Vendor ID")]) -> Result:
    """Get a vendor by ID."""
    return await get_client().get(f"/vendors/{vendor_id}")


# --- Products ------------------------------------------------------------------------------------

ProductId = Annotated[int, Field(description="Product ID")]
ProductStatus = Literal["In Production", "In Pipeline", "Retired"]
STATUS_BY_CODE = {1: "In Production", 2: "In Pipeline", 3: "Retired"}


def _product_status(value: ProductStatus | int | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, int):
        if value not in STATUS_BY_CODE:
            raise ToolError("status must be 1 (In Production), 2 (In Pipeline) or 3 (Retired)")
        return STATUS_BY_CODE[value]
    return value


@ts.tool("List products")
async def get_all_products(page: Page = 1, per_page: PerPage = 30) -> Result:
    """List catalogue products."""
    return await get_client().list("/products", "products", page=page, per_page=per_page)


@ts.tool("Get product")
async def get_product(product_id: ProductId) -> Result:
    """Get a product by ID."""
    return await get_client().get(f"/products/{product_id}")


@ts.tool("Create product", "create")
async def create_product(
    name: Annotated[str, Field(min_length=1, description="Product name")],
    asset_type_id: Annotated[int, Field(description="Asset type ID (see list_asset_types)")],
    manufacturer: Annotated[str | None, Field()] = None,
    status: Annotated[ProductStatus | int | None, Field(description="Name, or 1/2/3")] = None,
    mode_of_procurement: Annotated[str | None, Field(description="'Buy' or 'Lease'")] = None,
    depreciation_type_id: Annotated[int | None, Field()] = None,
    description: Annotated[str | None, Field(description="HTML description")] = None,
) -> Result:
    """Create a product."""
    payload = clean(
        {
            "name": name,
            "asset_type_id": asset_type_id,
            "manufacturer": manufacturer,
            "status": _product_status(status),
            "mode_of_procurement": mode_of_procurement,
            "depreciation_type_id": depreciation_type_id,
            "description": description,
        }
    )
    return await get_client().post("/products", payload)


@ts.tool("Update product", "update")
async def update_product(
    product_id: ProductId,
    name: Annotated[str | None, Field()] = None,
    asset_type_id: Annotated[int | None, Field()] = None,
    manufacturer: Annotated[str | None, Field()] = None,
    status: Annotated[ProductStatus | int | None, Field(description="Name, or 1/2/3")] = None,
    mode_of_procurement: Annotated[str | None, Field()] = None,
    depreciation_type_id: Annotated[int | None, Field()] = None,
    description: Annotated[str | None, Field()] = None,
) -> Result:
    """Update a product. Only the supplied fields change."""
    payload = clean(
        {
            "name": name,
            "asset_type_id": asset_type_id,
            "manufacturer": manufacturer,
            "status": _product_status(status),
            "mode_of_procurement": mode_of_procurement,
            "depreciation_type_id": depreciation_type_id,
            "description": description,
        }
    )
    if not payload:
        raise ToolError("No fields provided for update")
    return await get_client().put(f"/products/{product_id}", payload)


@ts.tool("Delete product", "delete")
async def delete_product(product_id: ProductId) -> Result:
    """Delete a product."""
    return await get_client().delete(f"/products/{product_id}")
