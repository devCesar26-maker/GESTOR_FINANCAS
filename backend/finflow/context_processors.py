"""Context processor do FinFlow: expõe o nonce CSP atual aos templates.

Qualquer template Django que precise renderizar um <script> inline usa:

    <script nonce="{{ csp_nonce }}">...</script>

O nonce é único por requisição (gerado no CSPFrameAncestorsMiddleware) e o
mesmo valor vai no header Content-Security-Policy via placeholder
{{CSP_NONCE}} — só scripts com este nonce exato executam.
"""


def csp(request):
    return {"csp_nonce": getattr(request, "csp_nonce", "")}
