(function () {
    function getEditor(toolbar) {
        if (!toolbar) return null;
        var selector = toolbar.dataset.editorSelector || '';
        if (!selector) return null;
        var scope = toolbar.closest('.modal-content, form, .comm-compose-email-card, .omni-chat-input-area, body') || document;
        return scope.querySelector(selector) || document.querySelector(selector);
    }

    function saveSelection(editor) {
        if (!editor) return;
        var sel = window.getSelection();
        if (!sel || sel.rangeCount === 0) return;
        var range = sel.getRangeAt(0);
        if (!editor.contains(range.commonAncestorContainer)) return;
        editor._commSavedRange = range.cloneRange();
    }

    function restoreSelection(editor) {
        if (!editor) return false;
        var sel = window.getSelection();
        if (!sel) return false;
        var range = editor._commSavedRange;
        if (!range) return false;
        try {
            sel.removeAllRanges();
            sel.addRange(range);
            return true;
        } catch (e) {
            return false;
        }
    }

    function focusEditor(editor) {
        if (!editor) return;
        editor.focus();
        if (!restoreSelection(editor)) {
            var range = document.createRange();
            range.selectNodeContents(editor);
            range.collapse(false);
            var sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(range);
            editor._commSavedRange = range.cloneRange();
        }
    }

    function exec(editor, command, value) {
        if (!editor || !command) return;
        focusEditor(editor);
        try {
            document.execCommand('styleWithCSS', false, true);
        } catch (e) {}
        document.execCommand(command, false, value || null);
        saveSelection(editor);
    }

    function wireEditorSelection(editor) {
        if (!editor || editor.dataset.commRichTextBound === '1') return;
        editor.dataset.commRichTextBound = '1';
        ['keyup', 'mouseup', 'focus', 'input'].forEach(function (eventName) {
            editor.addEventListener(eventName, function () {
                saveSelection(editor);
            });
        });
    }

    function bindToolbar(toolbar) {
        if (!toolbar || toolbar.dataset.commToolbarBound === '1') return;
        toolbar.dataset.commToolbarBound = '1';

        var editor = getEditor(toolbar);
        wireEditorSelection(editor);

        toolbar.querySelectorAll('[data-command]').forEach(function (control) {
            var eventName = control.tagName === 'SELECT' || control.type === 'color' ? 'change' : 'click';
            control.addEventListener(eventName, function (event) {
                event.preventDefault();
                var currentEditor = getEditor(toolbar);
                wireEditorSelection(currentEditor);
                if (!currentEditor) return;

                var command = control.dataset.command;
                var value = control.dataset.value || control.value || '';

                if (command === 'createLink') {
                    value = window.prompt('Ingresá la URL', 'https://') || '';
                    if (!value) return;
                }

                exec(currentEditor, command, value);

                if (control.tagName === 'SELECT') {
                    control.selectedIndex = 0;
                }
            });
        });
    }

    function initRichTextToolbars(root) {
        (root || document).querySelectorAll('.comm-rich-text-toolbar').forEach(bindToolbar);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            initRichTextToolbars(document);
        });
    } else {
        initRichTextToolbars(document);
    }

    document.body.addEventListener('htmx:afterSwap', function (event) {
        initRichTextToolbars(event.target || document);
    });

    window.commInitRichTextToolbars = initRichTextToolbars;
})();
