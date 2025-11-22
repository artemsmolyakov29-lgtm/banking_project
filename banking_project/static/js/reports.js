// static/js/reports.js

class ReportSystem {
    constructor() {
        this.currentReportType = null;
        this.exportQueue = [];
        this.isProcessing = false;
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadReportTemplates();
        this.initDashboard();
    }

    bindEvents() {
        // Обработка изменения типа отчета
        document.addEventListener('change', (e) => {
            if (e.target.name === 'report_type') {
                this.handleReportTypeChange(e.target.value);
            }
        });

        // Обработка предпросмотра
        document.addEventListener('click', (e) => {
            if (e.target.id === 'preview-btn' || e.target.closest('#preview-btn')) {
                this.previewReport();
            }
        });

        // Обработка отправки формы генерации отчета
        document.addEventListener('submit', (e) => {
            if (e.target.id === 'report-form') {
                this.handleReportGeneration(e);
            }
        });

        // Обработка фильтров дашборда
        document.addEventListener('submit', (e) => {
            if (e.target.id === 'dashboard-filters') {
                this.handleDashboardFilter(e);
            }
        });

        // Обработка экспорта данных
        document.addEventListener('submit', (e) => {
            if (e.target.id === 'export-form') {
                this.handleExport(e);
            }
        });
    }

    // Динамическая загрузка параметров отчета
    handleReportTypeChange(reportType) {
        this.currentReportType = reportType;

        // Скрываем все группы параметров
        document.querySelectorAll('.parameter-group').forEach(group => {
            group.style.display = 'none';
        });

        // Показываем соответствующую группу параметров
        const targetGroup = document.getElementById(`${reportType}-parameters`);
        if (targetGroup) {
            targetGroup.style.display = 'block';
            this.animateElement(targetGroup, 'fadeIn');
        }

        // Загружаем дополнительные параметры
        this.loadReportParameters(reportType);
    }

    async loadReportParameters(reportType) {
        try {
            this.showLoading('Загрузка параметров...');

            const response = await fetch(`/reports/api/parameters/${reportType}/`);
            const parameters = await response.json();

            this.renderParameters(parameters);
            this.hideLoading();
        } catch (error) {
            console.error('Ошибка загрузки параметров:', error);
            this.showError('Не удалось загрузить параметры отчета');
            this.hideLoading();
        }
    }

    renderParameters(parameters) {
        const container = document.getElementById('dynamic-parameters');
        if (!container) return;

        container.innerHTML = '';

        parameters.forEach(param => {
            const element = this.createParameterElement(param);
            container.appendChild(element);
        });

        this.animateElement(container, 'fadeIn');
    }

    createParameterElement(param) {
        const div = document.createElement('div');
        div.className = 'mb-3';

        switch (param.type) {
            case 'select':
                div.innerHTML = `
                    <label for="${param.name}" class="form-label">${param.label}</label>
                    <select class="form-select" id="${param.name}" name="${param.name}">
                        ${param.options.map(opt => 
                            `<option value="${opt.value}">${opt.label}</option>`
                        ).join('')}
                    </select>
                `;
                break;
            case 'checkbox':
                div.innerHTML = `
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" id="${param.name}" name="${param.name}">
                        <label class="form-check-label" for="${param.name}">${param.label}</label>
                    </div>
                `;
                break;
            case 'date':
                div.innerHTML = `
                    <label for="${param.name}" class="form-label">${param.label}</label>
                    <input type="date" class="form-control" id="${param.name}" name="${param.name}">
                `;
                break;
            default:
                div.innerHTML = `
                    <label for="${param.name}" class="form-label">${param.label}</label>
                    <input type="text" class="form-control" id="${param.name}" name="${param.name}">
                `;
        }

        return div;
    }

    // Предпросмотр данных
    async previewReport() {
        const formData = this.getFormData('report-form');

        try {
            this.showLoading('Формирование предпросмотра...');

            const response = await fetch('/reports/api/preview/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify(formData)
            });

            const previewData = await response.json();
            this.renderPreview(previewData);
            this.hideLoading();
        } catch (error) {
            console.error('Ошибка предпросмотра:', error);
            this.showError('Не удалось сформировать предпросмотр');
            this.hideLoading();
        }
    }

    renderPreview(data) {
        const previewModal = this.getOrCreatePreviewModal();
        const previewContent = document.getElementById('preview-content');

        if (data.table) {
            previewContent.innerHTML = this.createPreviewTable(data.table);
        } else if (data.chart) {
            previewContent.innerHTML = this.createPreviewChart(data.chart);
        } else {
            previewContent.innerHTML = '<p>Данные для предпросмотра недоступны</p>';
        }

        // Показываем модальное окно
        const modal = new bootstrap.Modal(previewModal);
        modal.show();
    }

    createPreviewTable(tableData) {
        return `
            <div class="table-responsive">
                <table class="table table-sm preview-table">
                    <thead>
                        <tr>
                            ${tableData.headers.map(header => `<th>${header}</th>`).join('')}
                        </tr>
                    </thead>
                    <tbody>
                        ${tableData.rows.map(row => `
                            <tr>
                                ${row.map(cell => `<td>${cell}</td>`).join('')}
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
            <div class="mt-3 text-muted small">
                Показано ${tableData.rows.length} из ${tableData.totalRecords || tableData.rows.length} записей
            </div>
        `;
    }

    createPreviewChart(chartData) {
        const canvasId = 'preview-chart-' + Date.now();
        return `
            <div class="chart-container">
                <canvas id="${canvasId}"></canvas>
            </div>
            <script>
                setTimeout(() => {
                    const ctx = document.getElementById('${canvasId}').getContext('2d');
                    new Chart(ctx, ${JSON.stringify(chartData)});
                }, 100);
            </script>
        `;
    }

    // Управление дашбордом
    initDashboard() {
        if (!document.getElementById('analytics-dashboard')) return;

        this.loadDashboardData();
        this.setupDashboardAutoRefresh();
    }

    async loadDashboardData(filters = {}) {
        try {
            this.showDashboardLoading();

            const response = await fetch('/reports/api/dashboard/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify(filters)
            });

            const dashboardData = await response.json();
            this.renderDashboard(dashboardData);
            this.hideDashboardLoading();
        } catch (error) {
            console.error('Ошибка загрузки дашборда:', error);
            this.showError('Не удалось загрузить данные дашборда');
            this.hideDashboardLoading();
        }
    }

    renderDashboard(data) {
        // Обновляем KPI карточки
        this.updateKPICards(data.kpi);

        // Обновляем графики
        this.updateCharts(data.charts);

        // Обновляем таблицы
        this.updateTables(data.tables);
    }

    updateKPICards(kpiData) {
        Object.keys(kpiData).forEach(kpiKey => {
            const card = document.querySelector(`[data-kpi="${kpiKey}"]`);
            if (card) {
                const valueElement = card.querySelector('.kpi-value');
                const trendElement = card.querySelector('.kpi-trend');

                if (valueElement) valueElement.textContent = kpiData[kpiKey].value;
                if (trendElement) {
                    trendElement.textContent = kpiData[kpiKey].trend;
                    trendElement.className = `kpi-trend ${kpiData[kpiKey].trend > 0 ? 'text-success' : 'text-danger'}`;
                }
            }
        });
    }

    updateCharts(chartsData) {
        chartsData.forEach(chartConfig => {
            const canvas = document.getElementById(chartConfig.canvasId);
            if (canvas) {
                const ctx = canvas.getContext('2d');

                // Уничтожаем старый график если существует
                if (canvas.chart) {
                    canvas.chart.destroy();
                }

                canvas.chart = new Chart(ctx, chartConfig);
            }
        });
    }

    updateTables(tablesData) {
        tablesData.forEach(tableConfig => {
            const container = document.getElementById(tableConfig.containerId);
            if (container) {
                container.innerHTML = this.createTableHTML(tableConfig);
            }
        });
    }

    setupDashboardAutoRefresh() {
        // Автообновление каждые 5 минут
        setInterval(() => {
            this.loadDashboardData();
        }, 300000);
    }

    // Очередь экспорта
    async handleExport(event) {
        event.preventDefault();

        const formData = this.getFormData('export-form');
        const exportJob = {
            id: 'export-' + Date.now(),
            type: formData.data_type,
            format: formData.format,
            status: 'queued',
            progress: 0
        };

        this.addToExportQueue(exportJob);
        await this.processExportQueue();
    }

    addToExportQueue(exportJob) {
        this.exportQueue.push(exportJob);
        this.renderExportQueue();
    }

    renderExportQueue() {
        const queueContainer = document.getElementById('export-queue');
        if (!queueContainer) return;

        queueContainer.innerHTML = this.exportQueue.map(job => `
            <div class="export-item ${job.status}" data-job-id="${job.id}">
                <div class="export-info">
                    <strong>${this.getExportTypeLabel(job.type)}</strong>
                    <span class="export-format-badge">${job.format.toUpperCase()}</span>
                </div>
                <div class="export-status">
                    <span class="status-text">${this.getStatusLabel(job.status)}</span>
                    ${job.status === 'processing' ? `
                        <div class="export-progress">
                            <div class="export-progress-bar" style="width: ${job.progress}%"></div>
                        </div>
                    ` : ''}
                </div>
            </div>
        `).join('');
    }

    async processExportQueue() {
        if (this.isProcessing || this.exportQueue.length === 0) return;

        this.isProcessing = true;

        while (this.exportQueue.length > 0) {
            const job = this.exportQueue[0];

            try {
                await this.processExportJob(job);
                this.exportQueue.shift(); // Удаляем завершенную задачу
            } catch (error) {
                console.error('Ошибка экспорта:', error);
                job.status = 'failed';
                this.renderExportQueue();
                break;
            }
        }

        this.isProcessing = false;
    }

    async processExportJob(job) {
        job.status = 'processing';
        this.renderExportQueue();

        // Имитация процесса экспорта
        for (let progress = 0; progress <= 100; progress += 10) {
            job.progress = progress;
            this.renderExportQueue();
            await this.delay(500);
        }

        job.status = 'completed';
        this.renderExportQueue();

        // Скачивание файла
        this.downloadExportResult(job);
    }

    downloadExportResult(job) {
        // В реальном приложении здесь будет запрос на скачивание файла
        console.log(`Скачивание экспорта: ${job.type}.${job.format}`);
    }

    // Вспомогательные методы
    getFormData(formId) {
        const form = document.getElementById(formId);
        const formData = new FormData(form);
        const data = {};

        for (let [key, value] of formData.entries()) {
            data[key] = value;
        }

        return data;
    }

    getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]').value;
    }

    showLoading(message = 'Загрузка...') {
        // Реализация показа индикатора загрузки
        const loadingElement = document.createElement('div');
        loadingElement.className = 'loading-overlay';
        loadingElement.innerHTML = `
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">${message}</span>
            </div>
        `;
        document.body.appendChild(loadingElement);
    }

    hideLoading() {
        const loadingElement = document.querySelector('.loading-overlay');
        if (loadingElement) {
            loadingElement.remove();
        }
    }

    showError(message) {
        // Показываем уведомление об ошибке
        const alert = document.createElement('div');
        alert.className = 'alert alert-danger alert-dismissible fade show';
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.querySelector('main').prepend(alert);
    }

    animateElement(element, animation) {
        element.classList.add(animation);
        setTimeout(() => {
            element.classList.remove(animation);
        }, 500);
    }

    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    getExportTypeLabel(type) {
        const types = {
            'clients': 'Данные клиентов',
            'transactions': 'Транзакции',
            'financial': 'Финансовые данные',
            'operations': 'Операционные данные',
            'analytics': 'Аналитические данные'
        };
        return types[type] || type;
    }

    getStatusLabel(status) {
        const statuses = {
            'queued': 'В очереди',
            'processing': 'Обработка',
            'completed': 'Завершено',
            'failed': 'Ошибка'
        };
        return statuses[status] || status;
    }

    getOrCreatePreviewModal() {
        let modal = document.getElementById('preview-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'preview-modal';
            modal.className = 'modal fade';
            modal.innerHTML = `
                <div class="modal-dialog modal-xl">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Предпросмотр отчета</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div id="preview-content"></div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Закрыть</button>
                            <button type="button" class="btn btn-primary" onclick="reportSystem.downloadPreview()">Скачать</button>
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }
        return modal;
    }

    // Загрузка шаблонов отчетов
    async loadReportTemplates() {
        try {
            const response = await fetch('/reports/api/templates/');
            const templates = await response.json();
            this.renderTemplates(templates);
        } catch (error) {
            console.error('Ошибка загрузки шаблонов:', error);
        }
    }

    renderTemplates(templates) {
        const container = document.getElementById('report-templates');
        if (!container) return;

        container.innerHTML = templates.map(template => `
            <div class="col-md-4 mb-3">
                <div class="card template-card h-100">
                    <div class="card-body">
                        <h6 class="card-title">${template.name}</h6>
                        <p class="card-text small text-muted">${template.description}</p>
                        <div class="template-meta">
                            <span class="badge bg-info">${template.type}</span>
                            <small class="text-muted">${template.last_used}</small>
                        </div>
                    </div>
                    <div class="card-footer">
                        <button class="btn btn-sm btn-outline-primary" onclick="reportSystem.loadTemplate(${template.id})">
                            Использовать
                        </button>
                    </div>
                </div>
            </div>
        `).join('');
    }

    async loadTemplate(templateId) {
        try {
            const response = await fetch(`/reports/api/templates/${templateId}/`);
            const template = await response.json();

            // Заполняем форму параметрами шаблона
            this.fillFormWithTemplate(template);

            this.showSuccess('Шаблон успешно загружен');
        } catch (error) {
            console.error('Ошибка загрузки шаблона:', error);
            this.showError('Не удалось загрузить шаблон');
        }
    }

    fillFormWithTemplate(template) {
        Object.keys(template.parameters).forEach(key => {
            const element = document.querySelector(`[name="${key}"]`);
            if (element) {
                element.value = template.parameters[key];
            }
        });
    }

    showSuccess(message) {
        const alert = document.createElement('div');
        alert.className = 'alert alert-success alert-dismissible fade show';
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.querySelector('main').prepend(alert);
    }

    // Обработчики событий дашборда
    handleDashboardFilter(event) {
        event.preventDefault();
        const formData = this.getFormData('dashboard-filters');
        this.loadDashboardData(formData);
    }

    showDashboardLoading() {
        const dashboard = document.getElementById('analytics-dashboard');
        if (dashboard) {
            dashboard.classList.add('loading');
        }
    }

    hideDashboardLoading() {
        const dashboard = document.getElementById('analytics-dashboard');
        if (dashboard) {
            dashboard.classList.remove('loading');
        }
    }
}

// Инициализация системы отчетности при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    window.reportSystem = new ReportSystem();
});

// Глобальные функции для использования в шаблонах
function refreshDashboard() {
    if (window.reportSystem) {
        window.reportSystem.loadDashboardData();
    }
}

function exportDashboard(format = 'png') {
    if (window.reportSystem) {
        // Реализация экспорта дашборда
        console.log(`Экспорт дашборда в формате: ${format}`);
    }
}

function previewReportData() {
    if (window.reportSystem) {
        window.reportSystem.previewReport();
    }
}