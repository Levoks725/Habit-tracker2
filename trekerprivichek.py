import flet as ft
from datetime import date, timedelta
import json

# ---------------------------------------------------------
# ХЕЛПЕРЫ
# ---------------------------------------------------------

def today_str() -> str:
    return date.today().isoformat()

def calc_streak(dates: list[str]) -> int:
    if not dates:
        return 0
    parsed = sorted({date.fromisoformat(d) for d in dates}, reverse=True)
    today = date.today()
    if parsed[0] not in (today, today - timedelta(days=1)):
        return 0
    streak = 1
    for prev, cur in zip(parsed, parsed[1:]):
        if (prev - cur).days == 1:
            streak += 1
        else:
            break
    return streak

def calc_best_streak(dates: list[str]) -> int:
    if not dates:
        return 0
    parsed = sorted({date.fromisoformat(d) for d in dates})
    best = cur = 1
    for prev, nxt in zip(parsed, parsed[1:]):
        if (nxt - prev).days == 1:
            cur += 1
            best = max(best, cur)
        else:
            cur = 1
    return best

# Палитра цветов — берём из ft.Colors
COLOR_PALETTE = [
    "BLUE", "GREEN", "ORANGE", "PURPLE", "PINK",
    "TEAL", "INDIGO", "RED", "AMBER", "CYAN",
]

def color_of(name: str):
    return getattr(ft.Colors, name, ft.Colors.BLUE)

def color_light(name: str):
    # Светлый вариант для «пустых» ячеек — используем 100-й оттенок если есть
    c = getattr(ft.Colors, f"{name}_100", None)
    return c or ft.Colors.GREY_300


async def main(page: ft.Page):
    page.title = "Habit Tracker"
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.scroll = ft.ScrollMode.AUTO

    prefs = ft.SharedPreferences()

    # ---------------------------------------------------------
    # ЗАГРУЗКА
    # ---------------------------------------------------------
    raw = await prefs.get("habits")
    if raw:
        habits: list[dict] = json.loads(raw)
    else:
        old_name = (await prefs.get("habit_name") or "").strip()
        try:
            old_days = int(await prefs.get("habit_days") or 0)
        except (TypeError, ValueError):
            old_days = 0
        habits = []
        if old_name:
            hist = [(date.today() - timedelta(days=i)).isoformat()
                    for i in range(old_days)]
            habits = [{"name": old_name, "goal": 21, "history": hist,
                       "color": "BLUE", "collapsed": False}]

    # Дозаполняем недостающие поля у старых записей
    for h in habits:
        h.setdefault("color", "BLUE")
        h.setdefault("collapsed", False)
        h.setdefault("history", [])
        h.setdefault("goal", 21)

    # Глобальная настройка длины календаря
    try:
        calendar_days = int(await prefs.get("calendar_days") or 30)
    except (TypeError, ValueError):
        calendar_days = 30
    if calendar_days not in (30, 90, 365):
        calendar_days = 30

    # Undo-стек
    undo_stack: list[tuple[str, callable]] = []

    async def save_habits():
        await prefs.set("habits", json.dumps(habits, ensure_ascii=False))

    async def save_calendar_days():
        await prefs.set("calendar_days", calendar_days)

    def push_undo(label: str, rollback):
        undo_stack.append((label, rollback))
        if len(undo_stack) > 30:
            undo_stack.pop(0)

    def show_undo_snackbar(label: str):
        async def do_undo(e):
            await perform_undo()

        page.show_dialog(ft.SnackBar(
            content=ft.Text(label),
            action="Отменить (Ctrl+Z)",
            on_action=do_undo,
        ))

    async def perform_undo():
        if not undo_stack:
            page.show_dialog(ft.SnackBar(content=ft.Text("Нечего отменять")))
            return
        label, rollback = undo_stack.pop()
        try:
            rollback()
        except Exception as ex:
            page.show_dialog(ft.SnackBar(content=ft.Text(f"Ошибка undo: {ex}")))
            return
        await save_habits()
        render()
        page.show_dialog(ft.SnackBar(content=ft.Text(f"Отменено: {label}")))

    # ---------------------------------------------------------
    # ФОРМА ДОБАВЛЕНИЯ
    # ---------------------------------------------------------
    name_input = ft.TextField(label="Название", width=200, dense=True)
    goal_input = ft.TextField(
        label="Цель", value="21", width=90, dense=True,
        keyboard_type=ft.KeyboardType.NUMBER,
    )

    # Выбор цвета — горизонтальная палитра
    new_color = {"value": "BLUE"}

    def build_palette(selected_holder: dict) -> ft.Control:
        swatches = []
        for cname in COLOR_PALETTE:
            async def pick(e, cn=cname):
                selected_holder["value"] = cn
                # обновляем обводку
                for sw in swatches:
                    sw.border = (
                        ft.Border.all(3, ft.Colors.BLACK)
                        if sw.data == cn else None
                    )
                page.update()

            sw = ft.Container(
                width=22, height=22, border_radius=11,
                bgcolor=color_of(cname),
                data=cname,
                on_click=pick,
                ink=True,
                border=ft.Border.all(3, ft.Colors.BLACK)
                if cname == selected_holder["value"] else None,
            )
            swatches.append(sw)
        return ft.Row(swatches, spacing=6, wrap=True)

    palette_row = build_palette(new_color)

    # Переключатель длины календаря
    async def set_calendar_days(e):
        nonlocal calendar_days
        calendar_days = int(e.control.data)
        await save_calendar_days()
        render()

    calendar_switcher = ft.Row([
        ft.Text("Календарь:", size=12, color=ft.Colors.GREY),
        *[
            ft.TextButton(
                content=ft.Text(f"{d} дн."),
                data=d,
                on_click=set_calendar_days,
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.BLUE_100 if calendar_days == d else None,
                ),
            )
            for d in (30, 90, 365)
        ],
    ], spacing=4)

    habits_list = ft.Column(spacing=12, width=600)

    # ---------------------------------------------------------
    # ДИАЛОГИ
    # ---------------------------------------------------------
    def confirm_delete(idx: int, name: str):
        async def do_delete(e):
            page.pop_dialog()
            removed = habits.pop(idx)
            push_undo(f"удаление «{name}»",
                      lambda: habits.insert(idx, removed))
            await save_habits()
            render()
            show_undo_snackbar(f"Удалена «{name}»")

        page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("Удалить привычку?"),
            content=ft.Text(f"«{name}» и вся история будут удалены."),
            actions=[
                ft.TextButton("Отмена", on_click=lambda e: page.pop_dialog()),
                ft.FilledButton("Удалить", on_click=do_delete,
                                bgcolor=ft.Colors.RED_500),
            ],
        ))

    def open_edit_dialog(idx: int):
        h = habits[idx]
        edit_name = ft.TextField(label="Название", value=h["name"], width=300)
        edit_goal = ft.TextField(
            label="Цель (дней)", value=str(h["goal"]), width=300,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        edit_color_holder = {"value": h.get("color", "BLUE")}
        edit_palette = build_palette(edit_color_holder)

        async def save_edit(e):
            new_name = (edit_name.value or "").strip()
            if not new_name:
                edit_name.error_text = "Введите название"
                page.update()
                return
            try:
                new_goal = max(1, int(edit_goal.value or 21))
            except ValueError:
                new_goal = 21

            old = {
                "name": h["name"],
                "goal": h["goal"],
                "color": h.get("color", "BLUE"),
            }
            h["name"] = new_name
            h["goal"] = new_goal
            h["color"] = edit_color_holder["value"]
            page.pop_dialog()
            await save_habits()

            def rollback():
                habits[idx].update(old)
            push_undo(f"редактирование «{new_name}»", rollback)
            render()
            show_undo_snackbar(f"Изменена «{new_name}»")

        page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("Редактировать привычку"),
            content=ft.Column([
                edit_name, edit_goal,
                ft.Text("Цвет", size=12, color=ft.Colors.GREY),
                edit_palette,
            ], tight=True, spacing=10),
            actions=[
                ft.TextButton("Отмена", on_click=lambda e: page.pop_dialog()),
                ft.FilledButton("Сохранить", on_click=save_edit),
            ],
        ))

    # ---------------------------------------------------------
    # КАЛЕНДАРЬ-СЕТКА
    # ---------------------------------------------------------
    def build_heatmap(idx: int, history: list[str], color_name: str) -> ft.Control:
        today = date.today()
        cells = []
        filled_color = color_of(color_name)
        empty_color = color_light(color_name)

        # 365 дней в строку не влезут — wrap решает
        for i in range(calendar_days - 1, -1, -1):
            d = today - timedelta(days=i)
            s = d.isoformat()
            done = s in history

            async def toggle(e, d_iso=s, idx=idx):
                hist = habits[idx]["history"]
                if d_iso in hist:
                    hist.remove(d_iso)
                    push_undo(f"снятие отметки {d_iso}",
                              lambda: hist.append(d_iso))
                    await save_habits()
                    render()
                else:
                    hist.append(d_iso)
                    push_undo(f"отметка {d_iso}",
                              lambda: hist.remove(d_iso))
                    await save_habits()
                    render()

            cell = ft.Container(
                width=16, height=16, border_radius=4,
                bgcolor=filled_color if done else empty_color,
                tooltip=f"{d.strftime('%d.%m.%Y')} — "
                        f"{'отмечено' if done else 'не отмечено'}",
                on_click=toggle,
                ink=True,
                data=done,
            )

            # Hover-эффект: увеличиваем через on_hover (доступно в новых Flet)
            async def on_hover(e, c=cell):
                if e.data == "true":
                    c.scale = 1.3
                    c.border = ft.Border.all(1, ft.Colors.BLACK)
                else:
                    c.scale = 1.0
                    c.border = None
                page.update()

            try:
                cell.on_hover = on_hover
            except Exception:
                pass  # старые версии Flet могут не поддерживать

            cells.append(cell)

        # Заголовок с легендой
        legend = ft.Row([
            ft.Text(f"{calendar_days} дней", size=11, color=ft.Colors.GREY),
            ft.Container(width=10, height=10, bgcolor=filled_color,
                         border_radius=2),
            ft.Text("отмечено", size=10, color=ft.Colors.GREY),
            ft.Container(width=10, height=10, bgcolor=empty_color,
                         border_radius=2),
            ft.Text("пропуск", size=10, color=ft.Colors.GREY),
        ], spacing=4)

        return ft.Column([
            legend,
            ft.Row(cells, spacing=3, wrap=True),
        ], spacing=6)

    # ---------------------------------------------------------
    # КАРТОЧКА
    # ---------------------------------------------------------
    def build_card(idx: int, habit: dict) -> ft.Control:
        history = habit.get("history", [])
        goal = habit.get("goal", 21)
        color_name = habit.get("color", "BLUE")
        collapsed = habit.get("collapsed", False)
        done_today = today_str() in history
        streak = calc_streak(history)
        best = calc_best_streak(history)
        progress = min(len(history) / goal, 1.0) if goal else 0
        accent = color_of(color_name)

        async def toggle_today(e, idx=idx):
            hist = habits[idx]["history"]
            t = today_str()
            if t in hist:
                hist.remove(t)
                push_undo("снятие отметки за сегодня",
                          lambda: hist.append(t))
            else:
                hist.append(t)
                push_undo("отметка сегодня", lambda: hist.remove(t))
            await save_habits()
            render()

        async def toggle_collapsed(e, idx=idx):
            habits[idx]["collapsed"] = not habits[idx].get("collapsed", False)
            await save_habits()
            render()

        action_btn = ft.FilledButton(
            content=ft.Text("✓ Сегодня" if done_today else "+ Сегодня"),
            on_click=toggle_today,
            bgcolor=ft.Colors.GREEN_600 if done_today else accent,
        )

        # --- Шапка (общая для свёрнутой и развёрнутой) ---
        header = ft.Row([
            ft.Container(
                width=12, height=12, border_radius=6, bgcolor=accent,
            ),
            ft.Text(habit["name"], size=18,
                    weight=ft.FontWeight.W_600, expand=True),
            ft.Text(f"🔥 {streak}", size=16, weight=ft.FontWeight.BOLD,
                    color=ft.Colors.ORANGE_600 if streak else ft.Colors.GREY),
            ft.IconButton(
                icon=ft.Icons.EDIT_OUTLINED,
                tooltip="Редактировать",
                on_click=lambda e, i=idx: open_edit_dialog(i),
            ),
            ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                icon_color=ft.Colors.RED_400,
                tooltip="Удалить",
                on_click=lambda e, i=idx, n=habit["name"]:
                    confirm_delete(i, n),
            ),
            ft.IconButton(
                icon=ft.Icons.EXPAND_MORE if collapsed else ft.Icons.EXPAND_LESS,
                tooltip="Свернуть / развернуть",
                on_click=toggle_collapsed,
            ),
        ])

        # --- Свёрнутый вид ---
        if collapsed:
            return ft.Card(
                content=ft.Container(
                    padding=12,
                    content=header,
                    bgcolor=ft.Colors.with_opacity(0.04, accent),
                )
            )

        # --- Развёрнутый вид ---
        metrics = ft.Row([
            ft.Column([
                ft.Text("Streak", size=11, color=ft.Colors.GREY),
                ft.Text(f"🔥 {streak}", size=22, weight=ft.FontWeight.BOLD,
                        color=ft.Colors.ORANGE_600 if streak
                        else ft.Colors.GREY),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Column([
                ft.Text("Всего", size=11, color=ft.Colors.GREY),
                ft.Text(f"{len(history)} / {goal}", size=20,
                        weight=ft.FontWeight.BOLD),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Column([
                ft.Text("Рекорд", size=11, color=ft.Colors.GREY),
                ft.Text(f"🏆 {best}", size=20, weight=ft.FontWeight.BOLD),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        ], alignment=ft.MainAxisAlignment.SPACE_AROUND)

        return ft.Card(
            content=ft.Container(
                padding=16,
                content=ft.Column([
                    header,
                    metrics,
                    ft.ProgressBar(value=progress, color=accent),
                    build_heatmap(idx, history, color_name),
                    ft.Row([action_btn],
                           alignment=ft.MainAxisAlignment.END),
                ], spacing=10),
            ),
            color=ft.Colors.with_opacity(0.03, accent),
        )

    # ---------------------------------------------------------
    # РЕНДЕР
    # ---------------------------------------------------------
    def render():
        habits_list.controls.clear()

        if not habits:
            habits_list.controls.append(ft.Container(
                padding=40, alignment=ft.Alignment.CENTER,
                content=ft.Text("Пока нет привычек.\nДобавьте первую 👇",
                                size=16, color=ft.Colors.GREY,
                                text_align=ft.TextAlign.CENTER),
            ))
        else:
            for i, h in enumerate(habits):
                habits_list.controls.append(build_card(i, h))

        page.update()

    # ---------------------------------------------------------
    # ДОБАВЛЕНИЕ
    # ---------------------------------------------------------
    async def add_habit(e):
        name = (name_input.value or "").strip()
        if not name:
            name_input.error_text = "Введите название"
            page.update()
            return
        try:
            goal = max(1, int(goal_input.value or 21))
        except ValueError:
            goal = 21

        new_habit = {
            "name": name, "goal": goal, "history": [],
            "color": new_color["value"], "collapsed": False,
        }
        habits.append(new_habit)
        idx = len(habits) - 1
        push_undo(f"добавление «{name}»",
                  lambda: habits.pop(idx) if idx < len(habits) else None)
        name_input.value = ""
        name_input.error_text = None
        await save_habits()
        render()
        show_undo_snackbar(f"Добавлена «{name}»")

    name_input.on_submit = add_habit

    # ---------------------------------------------------------
    # CTRL+Z
    # ---------------------------------------------------------
    async def on_keyboard(e: ft.KeyboardEvent):
        if e.ctrl and e.key.lower() == "z":
            await perform_undo()

    page.on_keyboard_event = on_keyboard

    # ---------------------------------------------------------
    # ВЕРХНЯЯ ПАНЕЛЬ
    # ---------------------------------------------------------
    top_bar = ft.Container(
        padding=16,
        content=ft.Column([
            ft.Text("Мои привычки", size=24, weight=ft.FontWeight.BOLD),
            ft.Row([
                name_input, goal_input,
                ft.Column([
                    ft.Text("Цвет", size=11, color=ft.Colors.GREY),
                    palette_row,
                ], spacing=2),
                ft.FilledButton("Добавить", on_click=add_habit),
            ], wrap=True, spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.END),
            calendar_switcher,
            ft.Text("Подсказка: Ctrl+Z — отменить последнее действие",
                    size=11, color=ft.Colors.GREY),
        ]),
    )

    page.add(top_bar, ft.Divider(), habits_list)
    render()


ft.run(main)