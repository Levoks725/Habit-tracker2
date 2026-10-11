import flet as ft

async def main(page: ft.Page):
    # Заголовок приложения.
    page.title = "Habit Tracker"
    # Выравниваем содержимое страницы по центру.
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.CENTER

    # Инициализация хранилища данных.
    prefs = ft.SharedPreferences()

    # -----------------------------
    # ЗАГРУЗКА СОХРАНЁННЫХ ДАННЫХ
    # -----------------------------
    saved_days = await prefs.get("habit_days")
    if saved_days is None:
        saved_days = 0

    saved_name = await prefs.get("habit_name")
    if saved_name is None:
        saved_name = ""

    # -----------------------------
    # СОСТОЯНИЕ
    # -----------------------------
    state = {
        "days": saved_days,
        "goal": 21,
    }

    # -----------------------------
    # ЭЛЕМЕНТЫ ИНТЕРФЕЙСА
    # -----------------------------
    days_text = ft.Text(
        f"{state['days']} / {state['goal']}",
        size=32,
        weight=ft.FontWeight.BOLD,
    )

    counter_circle = ft.Container(
        width=220,
        height=220,
        content=days_text,
        alignment=ft.Alignment.CENTER,
        border_radius=110,
        border=ft.Border.all(width=4, color=ft.Colors.BLUE),
    )

    habit_input = ft.TextField(
        label="Название привычки",
        value=saved_name,
        width=320,
    )

    # -----------------------------
    # ВСПЛЫВАЮЩЕЕ ОКНО (ДИАЛОГ)
    # -----------------------------
    async def close_dialog(e):
        # 1. Закрываем диалоговое окно
        page.pop_dialog()
        
        # 2. ДОБАВЛЕНО: Сбрасываем счетчик к нулю
        state["days"] = 0
        days_text.value = f"0 / {state['goal']}"
        
        # 3. Сохраняем ноль в памяти приложения
        await prefs.set("habit_days", 0)
        
        # 4. Обновляем страницу, чтобы изменения отобразились
        page.update()

    dialog = ft.AlertDialog(
        modal=False,
        content=ft.Text(
            "Поздравляю привычка добавлена",
            size=20,
            weight=ft.FontWeight.W_500,
            text_align=ft.TextAlign.CENTER,
        ),
        actions=[
            ft.Button(content=ft.Text("Ура!"), on_click=close_dialog),
        ],
        actions_alignment=ft.MainAxisAlignment.CENTER,
    )

    # -----------------------------
    # СОХРАНЕНИЕ НАЗВАНИЯ
    # -----------------------------
    async def save_name(e):
        name = (habit_input.value or "").strip()
        await prefs.set("habit_name", name)

    habit_input.on_blur = save_name

    # -----------------------------
    # КНОПКА +1
    # -----------------------------
    async def add_day(e):
        if state["days"] < state["goal"]:
            state["days"] += 1
            days_text.value = f"{state['days']} / {state['goal']}"
            await prefs.set("habit_days", state["days"])
            
            # Если счетчик достиг 21, открываем окно
            if state["days"] == state["goal"]:
                page.show_dialog(dialog)
                
            page.update()

    # -----------------------------
    # КНОПКА СБРОСА
    # -----------------------------
    async def reset_days(e):
        state["days"] = 0
        days_text.value = f"0 / {state['goal']}"
        await prefs.set("habit_days", 0)
        page.update()

    # -----------------------------
    # СОБИРАЕМ СТРАНИЦУ
    # -----------------------------
    page.add(
        ft.Column(
            controls=[
                habit_input,
                ft.Container(height=30),
                counter_circle,
                ft.Container(height=30),
                ft.Row(
                    controls=[
                        ft.FilledButton(content=ft.Text("+1 день"), on_click=add_day),
                        ft.FilledButton(content=ft.Text("Сбросить"), on_click=reset_days),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=20,
        )
    )

ft.run(main)





