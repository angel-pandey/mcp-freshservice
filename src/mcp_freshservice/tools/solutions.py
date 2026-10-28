"""Knowledge base: solution categories, folders and articles."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.server.fastmcp.exceptions import ToolError
from pydantic import Field

from ..client import clean, get_client
from ._common import Page, PerPage, Result, WorkspaceId
from ._registry import toolset

ts = toolset("solutions", "Knowledge base categories, folders and articles", default=True)

CategoryId = Annotated[int, Field(description="Solution category ID")]
FolderId = Annotated[int, Field(description="Solution folder ID")]
ArticleId = Annotated[int, Field(description="Solution article ID")]
Trash = Annotated[Literal["trash"] | None, Field(description="Pass 'trash' to list deleted items")]
Visibility = Annotated[
    int,
    Field(
        ge=1,
        le=7,
        description="1 All users, 2 Logged-in users, 3 Agents, 4 Selected departments, "
        "5 Selected agent groups, 6 Selected requester groups, 7 Bots",
    ),
]


# --- Categories ----------------------------------------------------------------------------------


@ts.tool("List solution categories")
async def get_all_solution_category(
    page: Page = 1, per_page: PerPage = 30, workspace_id: WorkspaceId = None
) -> Result:
    """List knowledge-base categories."""
    client = get_client()
    params = {"workspace_id": client.workspace(workspace_id)}
    return await client.list(
        "/solutions/categories", "categories", page=page, per_page=per_page, params=params
    )


@ts.tool("Get solution category")
async def get_solution_category(category_id: CategoryId) -> Result:
    """Get a knowledge-base category by ID."""
    return await get_client().get(f"/solutions/categories/{category_id}")


@ts.tool("Create solution category", "create")
async def create_solution_category(
    name: Annotated[str, Field(min_length=1, description="Category name")],
    description: Annotated[str | None, Field()] = None,
    workspace_id: WorkspaceId = None,
) -> Result:
    """Create a knowledge-base category."""
    client = get_client()
    payload = clean(
        {"name": name, "description": description, "workspace_id": client.workspace(workspace_id)}
    )
    return await client.post("/solutions/categories", payload)


@ts.tool("Update solution category", "update")
async def update_solution_category(
    category_id: CategoryId,
    name: Annotated[str | None, Field()] = None,
    description: Annotated[str | None, Field()] = None,
    default_category: Annotated[bool | None, Field(description="Make this the default category")] = None,
) -> Result:
    """Update a knowledge-base category."""
    payload = clean({"name": name, "description": description, "default_category": default_category})
    if not payload:
        raise ToolError("No fields provided for update")
    return await get_client().put(f"/solutions/categories/{category_id}", payload)


@ts.tool("Delete solution category", "delete")
async def delete_solution_category(category_id: CategoryId) -> Result:
    """Move a category (and its folders and articles) to trash."""
    return await get_client().delete(f"/solutions/categories/{category_id}")


# --- Folders -------------------------------------------------------------------------------------


@ts.tool("List solution folders")
async def get_list_of_solution_folder(
    category_id: CategoryId, page: Page = 1, per_page: PerPage = 30, filter: Trash = None
) -> Result:
    """List the folders in a category."""
    params = {"category_id": category_id, "filter": filter}
    return await get_client().list(
        "/solutions/folders", "folders", page=page, per_page=per_page, params=params
    )


@ts.tool("List solution sub-folders")
async def list_solution_subfolders(folder_id: FolderId, page: Page = 1, per_page: PerPage = 30) -> Result:
    """List the sub-folders of a folder."""
    return await get_client().list(
        f"/solutions/folders/{folder_id}/sub-folders", "folders", page=page, per_page=per_page
    )


@ts.tool("Get solution folder")
async def get_solution_folder(folder_id: FolderId) -> Result:
    """Get a knowledge-base folder by ID."""
    return await get_client().get(f"/solutions/folders/{folder_id}")


@ts.tool("Create solution folder", "create")
async def create_solution_folder(
    name: Annotated[str, Field(min_length=1, description="Folder name")],
    category_id: CategoryId,
    visibility: Visibility = 4,
    description: Annotated[str | None, Field()] = None,
    parent_folder_id: Annotated[
        int | None, Field(description="Create as a sub-folder of this folder")
    ] = None,
    department_ids: Annotated[list[int] | None, Field(description="Required when visibility is 4")] = None,
    group_ids: Annotated[list[int] | None, Field(description="Required when visibility is 5")] = None,
    requester_group_ids: Annotated[
        list[int] | None, Field(description="Required when visibility is 6")
    ] = None,
) -> Result:
    """Create a knowledge-base folder."""
    required = {
        4: ("department_ids", department_ids),
        5: ("group_ids", group_ids),
        6: ("requester_group_ids", requester_group_ids),
    }
    if visibility in required and not required[visibility][1]:
        raise ToolError(f"{required[visibility][0]} is required when visibility is {visibility}")
    payload = clean(
        {
            "name": name,
            "category_id": category_id,
            "visibility": visibility,
            "description": description,
            "parent_folder_id": parent_folder_id,
            "department_ids": department_ids,
            "group_ids": group_ids,
            "requester_group_ids": requester_group_ids,
        }
    )
    return await get_client().post("/solutions/folders", payload)


@ts.tool("Update solution folder", "update")
async def update_solution_folder(
    folder_id: FolderId,
    name: Annotated[str | None, Field()] = None,
    description: Annotated[str | None, Field()] = None,
    visibility: Annotated[int | None, Field(ge=1, le=7, description="See create_solution_folder")] = None,
    department_ids: Annotated[list[int] | None, Field()] = None,
    group_ids: Annotated[list[int] | None, Field()] = None,
    requester_group_ids: Annotated[list[int] | None, Field()] = None,
) -> Result:
    """Update a knowledge-base folder."""
    payload = clean(
        {
            "name": name,
            "description": description,
            "visibility": visibility,
            "department_ids": department_ids,
            "group_ids": group_ids,
            "requester_group_ids": requester_group_ids,
        }
    )
    if not payload:
        raise ToolError("No fields provided for update")
    return await get_client().put(f"/solutions/folders/{folder_id}", payload)


@ts.tool("Delete solution folder", "delete")
async def delete_solution_folder(folder_id: FolderId) -> Result:
    """Move a folder (and its articles) to trash."""
    return await get_client().delete(f"/solutions/folders/{folder_id}")


# --- Articles ------------------------------------------------------------------------------------


SNIPPET_CHARS = 300
IncludeBody = Annotated[
    bool,
    Field(
        description="Return each article's full HTML and text body instead of a short snippet. "
        "Large: 30 articles can run to tens of thousands of tokens. Prefer get_solution_article."
    ),
]


def _compact(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Swap the full bodies for a short plain-text snippet; everything else is kept."""
    out = []
    for article in articles:
        text = (article.get("description_text") or "").strip()
        slim = {k: v for k, v in article.items() if k not in ("description", "description_text")}
        slim["snippet"] = text if len(text) <= SNIPPET_CHARS else text[:SNIPPET_CHARS].rstrip() + "…"
        out.append(slim)
    return out


@ts.tool("List solution articles")
async def get_list_of_solution_article(
    folder_id: FolderId,
    page: Page = 1,
    per_page: PerPage = 30,
    filter: Trash = None,
    include_body: IncludeBody = False,
) -> Result:
    """List the articles in a folder: metadata plus a short plain-text `snippet`, not the full body.

    Use get_solution_article with an article id to read the whole article.
    """
    params = {"folder_id": folder_id, "filter": filter}
    result = await get_client().list(
        "/solutions/articles", "articles", page=page, per_page=per_page, params=params
    )
    if not include_body:
        result["articles"] = _compact(result["articles"])
    return result


@ts.tool("Search solution articles")
async def search_solution_articles(
    search_term: Annotated[str, Field(min_length=1, description="Words to look for")],
    page: Page = 1,
    per_page: PerPage = 30,
    user_email: Annotated[
        str | None, Field(description="Search on behalf of this user (respects visibility)")
    ] = None,
    include_body: IncludeBody = False,
) -> Result:
    """Full-text search across published knowledge-base articles.

    Each result has id, title, folder_id/category_id, status and a short plain-text `snippet` (the first
    ~300 characters). Freshservice returns every article's full body here, which makes 30 results very
    large, so they are trimmed unless include_body is true. To read an article, call get_solution_article
    with its id (full HTML in description, plain text in description_text).
    """
    params = {"search_term": search_term, "user_email": user_email}
    result = await get_client().list(
        "/solutions/articles/search", "articles", page=page, per_page=per_page, params=params
    )
    if not include_body:
        result["articles"] = _compact(result["articles"])
    return result


@ts.tool("Get solution article")
async def get_solution_article(article_id: ArticleId) -> Result:
    """Read a knowledge-base article by ID: the full HTML in description and plain text in description_text.

    Use the id from search_solution_articles or get_list_of_solution_article.
    """
    return await get_client().get(f"/solutions/articles/{article_id}")


@ts.tool("Create solution article", "create")
async def create_solution_article(
    title: Annotated[str, Field(min_length=1, description="Article title")],
    description: Annotated[str, Field(description="Article body (HTML)")],
    folder_id: FolderId,
    article_type: Annotated[int, Field(ge=1, le=2, description="1 Permanent, 2 Workaround")] = 1,
    status: Annotated[int, Field(ge=1, le=2, description="1 Draft, 2 Published")] = 1,
    tags: Annotated[list[str] | None, Field()] = None,
    keywords: Annotated[list[str] | None, Field()] = None,
    review_date: Annotated[str | None, Field(description="YYYY-MM-DD")] = None,
) -> Result:
    """Create a knowledge-base article (a draft unless status is 2)."""
    payload = clean(
        {
            "title": title,
            "description": description,
            "folder_id": folder_id,
            "article_type": article_type,
            "status": status,
            "tags": tags,
            "keywords": keywords,
            "review_date": review_date,
        }
    )
    return await get_client().post("/solutions/articles", payload)


@ts.tool("Update solution article", "update")
async def update_solution_article(
    article_id: ArticleId,
    title: Annotated[str | None, Field()] = None,
    description: Annotated[str | None, Field(description="HTML body")] = None,
    folder_id: Annotated[int | None, Field(description="Move to this folder")] = None,
    article_type: Annotated[int | None, Field(ge=1, le=2, description="1 Permanent, 2 Workaround")] = None,
    status: Annotated[int | None, Field(ge=1, le=2, description="1 Draft, 2 Published")] = None,
    tags: Annotated[list[str] | None, Field()] = None,
    keywords: Annotated[list[str] | None, Field()] = None,
    review_date: Annotated[str | None, Field(description="YYYY-MM-DD")] = None,
) -> Result:
    """Update a knowledge-base article."""
    payload = clean(
        {
            "title": title,
            "description": description,
            "folder_id": folder_id,
            "article_type": article_type,
            "status": status,
            "tags": tags,
            "keywords": keywords,
            "review_date": review_date,
        }
    )
    if not payload:
        raise ToolError("No fields provided for update")
    return await get_client().put(f"/solutions/articles/{article_id}", payload)


@ts.tool("Publish solution article", "update")
async def publish_solution_article(article_id: ArticleId) -> Result:
    """Publish a draft article (sets status to 2)."""
    return await get_client().put(f"/solutions/articles/{article_id}", {"status": 2})


@ts.tool("Delete solution article", "delete")
async def delete_solution_article(article_id: ArticleId) -> Result:
    """Move an article to trash."""
    return await get_client().delete(f"/solutions/articles/{article_id}")
