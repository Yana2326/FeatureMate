# KB Agent — Altegio Feature Documenter

AI-агент для автоматического создания статей базы знаний по новым фичам Altegio.

## Как работает

1. Заходит в тестовый аккаунт Altegio через Playwright
2. Переходит по указанному пути в интерфейсе
3. Анализирует страницу: тексты, кнопки, поля, переключатели
4. Делает скриншоты ключевых шагов
5. Генерирует черновик статьи на русском языке в Markdown
6. Сохраняет: статью `.md`, скриншоты, JSON-анализ страницы

## Установка

```bash
# 1. Создать виртуальное окружение
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Установить зависимости
pip install -r requirements.txt

# 3. Установить Playwright браузеры
npx playwright install chromium

# 4. Настроить переменные окружения
cp .env.example .env
# Заполнить .env своими данными
```

## Использование

```bash
# Базовый запуск
python agent.py --feature "Sell product" --path "Calendar → Sell product"

# С описанием фичи
python agent.py \
  --feature "Sell product" \
  --path "Calendar → Sell product" \
  --description "Продажа товаров прямо из карточки записи клиента"
```

### Параметры

| Параметр | Обязательный | Описание |
|---|---|---|
| `--feature` | Да | Название фичи |
| `--path` | Да | Путь в интерфейсе (например: `Calendar → Sell product`) |
| `--description` | Нет | Краткое описание для контекста |

## Структура выходных файлов

```
output/
└── sell_product/
    ├── article.md           # Статья базы знаний (русский, Markdown)
    ├── page_analysis.json   # JSON-анализ UI-элементов страницы
    ├── screenshots.md       # Список сделанных скриншотов
    └── *.png                # Скриншоты (сохраняются Playwright)
```

## Переменные окружения (.env)

```
ANTHROPIC_API_KEY=     # API-ключ Claude
ALTEGIO_EMAIL=         # Email тестового аккаунта Altegio
ALTEGIO_PASSWORD=      # Пароль тестового аккаунта
```
