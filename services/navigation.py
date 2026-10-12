"""Czyste reguły nawigacji modułów Streamlit."""


def available_modules(module_options, role):
    """Zwraca etykieta → identyfikator modułu dostępne dla roli."""
    return {
        label: config["id"]
        for label, config in module_options.items()
        if role in config.get("roles", [])
    }


def available_navigation_groups(module_groups, label_to_module):
    """Filtruje grupy oraz moduły, do których rola ma dostęp."""
    groups = {
        group: [label for label, module_id in label_to_module.items() if module_id in module_ids]
        for group, module_ids in module_groups.items()
    }
    return {group: labels for group, labels in groups.items() if labels}


def group_for_module_label(groups, module_label):
    """Określa grupę aktywnego modułu lub pierwszą dostępną grupę."""
    return next((group for group, labels in groups.items() if module_label in labels), next(iter(groups), ""))


def module_label_for_id(module_options, module_id):
    return next((label for label, config in module_options.items() if config.get("id") == module_id), None)


def group_for_module_id(module_groups, module_id, fallback=""):
    return next((group for group, ids in module_groups.items() if module_id in ids), fallback)
