from urllib.parse import urlencode


def build_folder_breadcrumbs(folder, list_url, root_label="All Notes", query_param="folder"):
    """Build breadcrumb links from root to the current folder."""
    breadcrumbs = [{"label": root_label, "url": list_url}]
    if not folder:
        return breadcrumbs

    ancestors = []
    current = folder
    while current:
        ancestors.insert(0, current)
        current = current.parent

    for ancestor in ancestors:
        if ancestor:
            url = f"{list_url}?{urlencode({query_param: ancestor.id})}"
            breadcrumbs.append({"label": ancestor.name, "url": url})
    return breadcrumbs
