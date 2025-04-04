// Кнопка "Наверх"
document.addEventListener('DOMContentLoaded', function() {
    // Создаем кнопку
    const backToTopButton = document.createElement('div');
    backToTopButton.className = 'back-to-top';
    backToTopButton.innerHTML = '↑';
    document.body.appendChild(backToTopButton);

    // Показываем/скрываем кнопку при прокрутке
    window.addEventListener('scroll', function() {
        if (window.pageYOffset > 300) {
            backToTopButton.style.display = 'block';
        } else {
            backToTopButton.style.display = 'none';
        }
    });

    // Плавная прокрутка при клике
    backToTopButton.addEventListener('click', function() {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });

    // Индикатор загрузки
    const loadingOverlay = document.createElement('div');
    loadingOverlay.className = 'loading';
    loadingOverlay.innerHTML = '<div class="loading-spinner"></div>';
    document.body.appendChild(loadingOverlay);

    // Показываем индикатор загрузки при переходе по ссылкам
    document.querySelectorAll('a').forEach(link => {
        link.addEventListener('click', function(e) {
            if (this.href && !this.href.startsWith('#')) {
                loadingOverlay.style.display = 'flex';
            }
        });
    });

    // Скрываем индикатор загрузки при загрузке страницы
    window.addEventListener('load', function() {
        loadingOverlay.style.display = 'none';
    });
}); 