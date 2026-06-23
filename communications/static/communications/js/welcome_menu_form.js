(function () {
    var container = document.getElementById('items-container');
    var addButton = document.getElementById('welcome-menu-add-item');
    var template = document.getElementById('welcome-menu-item-template');
    if (!container || !addButton || !template) return;

    var itemCount = parseInt(container.dataset.itemCount || '1', 10);
    if (!Number.isFinite(itemCount) || itemCount < 1) itemCount = 1;

    function addItem() {
        itemCount += 1;
        var html = template.innerHTML.replace(/__ITEM_NUMBER__/g, String(itemCount));
        container.insertAdjacentHTML('beforeend', html);
    }

    addButton.addEventListener('click', addItem);
})();
