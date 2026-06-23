(function () {
    var dropZone = document.getElementById('dropZone');
    var fileInput = document.getElementById('csv_file_input');
    var actualFileInput = document.getElementById('actual_file');
    var uploadStep = document.getElementById('uploadStep');
    var previewStep = document.getElementById('previewStep');

    if (!dropZone || !fileInput || !actualFileInput || !uploadStep || !previewStep) return;

    dropZone.addEventListener('click', function () { fileInput.click(); });
    fileInput.addEventListener('change', function () { handleFiles(fileInput.files); });
    dropZone.addEventListener('dragover', function (e) {
        e.preventDefault();
        dropZone.classList.add('bg-primary', 'bg-opacity-10');
    });
    dropZone.addEventListener('dragleave', function () {
        dropZone.classList.remove('bg-primary', 'bg-opacity-10');
    });
    dropZone.addEventListener('drop', function (e) {
        e.preventDefault();
        dropZone.classList.remove('bg-primary', 'bg-opacity-10');
        handleFiles(e.dataTransfer.files);
    });

    function handleFiles(files) {
        if (!files || files.length === 0) return;
        var file = files[0];
        var dataTransfer = new DataTransfer();
        dataTransfer.items.add(file);
        actualFileInput.files = dataTransfer.files;

        var reader = new FileReader();
        reader.onload = function (event) {
            processData(event.target.result);
        };
        reader.readAsText(file);
    }

    function processData(csvData) {
        var lines = csvData.split(/\r?\n/).filter(function (line) { return line.trim() !== ''; });
        if (!lines.length) return;

        var firstLine = lines[0];
        var delimiter = firstLine.indexOf(';') !== -1 ? ';' : ',';
        var headers = firstLine.split(delimiter).map(function (h) { return h.trim(); });
        var looksLikeHeaders = headers.some(function (h) {
            return ['nombre', 'name', 'email', 'telefono', 'phone'].indexOf(h.toLowerCase()) !== -1;
        });
        var defaultHeaders = ['Nombre', 'Email', 'Telefono', 'Empresa'];
        var displayHeaders = looksLikeHeaders ? headers : headers.map(function (_, i) {
            return defaultHeaders[i] || ('Columna ' + (i + 1));
        });
        var displayRows = looksLikeHeaders ? lines.slice(1, 11) : lines.slice(0, 10);

        document.getElementById('tableHeader').innerHTML = displayHeaders.map(function (h) {
            return '<th>' + h + '</th>';
        }).join('');
        document.getElementById('tableBody').innerHTML = displayRows.map(function (row) {
            var cols = row.split(delimiter);
            return '<tr>' + cols.map(function (c) { return '<td>' + c.trim() + '</td>'; }).join('') + '</tr>';
        }).join('');
        document.getElementById('rowCountBadge').textContent = (lines.length - (looksLikeHeaders ? 1 : 0)) + ' filas detectadas';
        uploadStep.classList.add('d-none');
        previewStep.classList.remove('d-none');
    }

    window.resetUpload = function () {
        uploadStep.classList.remove('d-none');
        previewStep.classList.add('d-none');
        fileInput.value = '';
    };
})();
