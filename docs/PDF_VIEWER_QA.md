# Exact source / PDF viewer QA

Offline automated checks include: local `/pdf/<file>.pdf` HTTP serve, PDF.js route `/pdfjs/web/viewer.html`, PDF path traversal rejection, original session/CSRF, and generated source link page anchors (`#page=N`) with URL HTML escaping. This is **route/markup testing using fixtures**; it does not prove all real ministry PDFs render in the browser.

Real-browser checks after install:
1. Expand a reviewed 2023 VGF version and click `মূল উৎস`, then the new `PDF পৃষ্ঠা N` link beside an exact quote.
2. Verify actual PDF content and page for `H01-*`; if the link is inaccessible, note document date, link and error without assuming a new policy rule.
3. Verify the original `/pdfjs/` viewer still opens a locally stored PDF and navigates to the requested page.
4. Confirm UI has no extra vertical whitespace between clause id and quote, and a historical result no longer advertises confirmed current policy.
