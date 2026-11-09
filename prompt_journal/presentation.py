"""Local SVG icons shared by every web surface."""

_PATHS = {
    'chart': '<path d="M4 3v17h17M8 16v-5m5 5V6m5 10V9"/>',
    'user': '<circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/>',
    'search': '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/>',
    'folder': '<path d="M3 7V5a1 1 0 0 1 1-1h5l3 3h8a1 1 0 0 1 1 1v11H3V7Z"/><path d="M3 9h18"/>',
    'arrow': '<path d="M4 12h15m-5-5 5 5-5 5"/>',
    'chevron': '<path d="m6 9 6 6 6-6"/>',
    'trash': '<path d="M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7"/>',
    'check': '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
    'keyboard': '<rect x="2.5" y="6" width="19" height="12" rx="2"/><path d="M6 10h.01M9 10h.01M12 10h.01M15 10h.01M18 10h.01M6 13h.01M9 13h.01M12 13h.01M15 13h.01M18 13h.01M8 16h8"/>',
}


def icon(name: str) -> str:
    if name == 'brand':
        return (
            '<svg class="icon" viewBox="0 0 32 32" aria-hidden="true" focusable="false">'
            '<path fill="currentColor" opacity=".35" d="M3 10h21v15H9l-6 5V10Z"/>'
            '<path fill="currentColor" d="M9 2h21v21H15l-6 5V2Z"/>'
            '<path stroke="white" stroke-width="1.7" stroke-linecap="round" d="M14 8h11M14 12h11M14 16h7"/>'
            '</svg>'
        )
    return (
        '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" '
        'aria-hidden="true" focusable="false">' + _PATHS[name] + '</svg>'
    )
