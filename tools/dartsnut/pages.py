import copy
import uuid


class PageConflictError(ValueError):
    pass


def page_uuid(widget_id: str, page_title: str) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"dartsnut-widget-page:{widget_id}:{page_title}",
        )
    )


def page_references_widget(page: dict[str, object], widget_id: str) -> bool:
    widgets = page.get("widgets", [])
    return isinstance(widgets, list) and any(
        isinstance(widget, dict) and widget.get("id") == widget_id
        for widget in widgets
    )


def new_widget_page(widget_id: str, page_title: str) -> dict[str, object]:
    return {
        "uuid": page_uuid(widget_id, page_title),
        "title": page_title,
        "duration": "15",
        "combination": "0",
        "enabled": True,
        "widgets": [
            {
                "id": widget_id,
                "position": [0, 0, 127, 127],
                "fields": {},
            }
        ],
        "wv": None,
    }


def upsert_widget_page(
    config: dict[str, object],
    widget_id: str,
    page_title: str,
) -> dict[str, object]:
    updated = copy.deepcopy(config)
    pages = updated.setdefault("pages", [])
    if not isinstance(pages, list):
        raise PageConflictError("apps/conf.json pages must be a list")

    expected_uuid = page_uuid(widget_id, page_title)
    matches = [
        page
        for page in pages
        if isinstance(page, dict)
        and (
            page_references_widget(page, widget_id)
            or page.get("uuid") == expected_uuid
        )
    ]
    if len(matches) > 1:
        raise PageConflictError(f"Multiple pages reference widget {widget_id}")
    if matches:
        page = matches[0]
        widgets = page.setdefault("widgets", [])
        if not isinstance(widgets, list):
            raise PageConflictError("Page widgets must be a list")
        if not page_references_widget(page, widget_id):
            widgets.append(
                {
                    "id": widget_id,
                    "position": [0, 0, 127, 127],
                    "fields": {},
                }
            )
        return updated

    title_match = next(
        (
            page
            for page in pages
            if isinstance(page, dict) and page.get("title") == page_title
        ),
        None,
    )
    if title_match is not None:
        raise PageConflictError(
            f"Page title {page_title!r} is already owned by another page"
        )
    pages.append(new_widget_page(widget_id, page_title))
    return updated


def remove_widget_reference(
    config: dict[str, object],
    widget_id: str,
    *,
    remove_empty_page: bool = False,
) -> dict[str, object]:
    updated = copy.deepcopy(config)
    pages = updated.get("pages", [])
    if not isinstance(pages, list):
        raise PageConflictError("apps/conf.json pages must be a list")

    kept_pages = []
    for page in pages:
        if not isinstance(page, dict) or not page_references_widget(page, widget_id):
            kept_pages.append(page)
            continue
        widgets = page.get("widgets", [])
        page["widgets"] = [
            widget
            for widget in widgets
            if not (isinstance(widget, dict) and widget.get("id") == widget_id)
        ]
        if page["widgets"] or not remove_empty_page:
            kept_pages.append(page)
    updated["pages"] = kept_pages
    return updated
