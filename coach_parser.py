import re


def parse_weight_update(text: str) -> float | None:
    """Распознаёт обновление веса атлета, например: 'мой вес 67.5' или 'вешу 68 кг'."""
    match = re.search(r"(?:мой\s+вес|вешу|вес\s+сейчас|текущий\s+вес)\s*[:=-]?\s*(\d{2,3}(?:[.,]\d{1,2})?)", text.lower())
    if match:
        return float(match.group(1).replace(",", "."))
    return None


def parse_workout_command(text: str) -> dict | None:
    """
    Разбирает ТОЛЬКО реальную живую диктовку выполненных подходов (с цифрами повторов/подходов).
    Игнорирует длинные отчёты о всей тренировке и разговорные фразы при обсуждении плана.
    """
    clean = text.strip()
    lower = clean.lower()

    # 1. Длинные отчёты с переносами строк или пунктами (1., 2.) отдаём в GigaChat для полной сверки
    if "\n" in clean or len(clean) > 140:
        return None

    # 2. Разговорные фразы обсуждения плана не считаем выполненным подходом
    planning_phrases = (
        "составь", "составим", "план", "тренировку", "давай сделаем",
        "давай так", "что делать", "посоветуй", "подбери", "какие упражнения", "?"
    )
    if any(p in lower for p in planning_phrases):
        return None

    # 3. Обязательно должны быть цифры повторов или паттерн подходов
    has_sets_pattern = bool(re.search(r"\d+\s*(?:по|x|х|\*)\s*\d+", lower)) or bool(re.search(r":\s*\d+", lower))
    has_reps_num = bool(re.search(r"(?:на\s+\d+|\b\d+\s*(?:раз|повтор))", lower))
    triggers = ("запиши", "добавь", "сохрани", "сделал", "выполнил", "пожал", "присел", "подтянулся", "подход")

    if not (has_sets_pattern or has_reps_num or any(re.search(rf"\b{t}\b", lower) for t in triggers)):
        return None

    # 4. Ищем рабочий вес (в кг)
    weight = 0.0
    weight_match = re.search(r"(?:с\s+весом|вес|гантел[ьяией]*|блин[ома]*|штанг[аойу]*|гир[яейю]*)?\s*(\d+(?:[.,]\d+)?)\s*кг", lower)
    if weight_match:
        weight = float(weight_match.group(1).replace(",", "."))

    text_no_weight = re.sub(
        r"(?:с\s+весом|вес|гантел[ьяией]*|блин[ома]*|штанг[аойу]*|гир[яейю]*)?\s*\d+(?:[.,]\d+)?\s*кг",
        " ",
        clean,
        flags=re.IGNORECASE
    )

    word_nums = {
        "один": "1", "первый": "1", "первом": "1",
        "два": "2", "второй": "2", "втором": "2",
        "три": "3", "третий": "3", "третьем": "3",
        "четыре": "4", "четвёртый": "4", "четвертый": "4", "четвёртом": "4",
        "пять": "5", "пятый": "5", "пятом": "5",
        "шесть": "6", "шестой": "6", "шестом": "6"
    }
    normalized = text_no_weight.lower()
    for word, digit in word_nums.items():
        normalized = re.sub(rf"\b{word}\b", digit, normalized)

    # 5. Очищаем название упражнения от разговорных вводных слов
    name_part = re.sub(
        r"^(?:так\s+|ну\s+|короче\s+|давай\s+|делаем\s+|запиши\s+|добавь\s+|сохрани\s+|я\s+сделал\s+|сделал\s+|выполнил\s+|ещё\s+|еще\s+|сейчас\s+)+",
        "",
        clean,
        flags=re.IGNORECASE
    )
    name_part = re.sub(r"^[1-6]\s*(?:подход)?\s*(?:на\s+[а-яё]+\s*)?[,.-]?\s*", "", name_part, flags=re.IGNORECASE)
    name_part = re.split(
        r"[:;]|\b\d+\s*(?:подход|по|повтор|раз|x|х|\*)|\b(?:один|два|три|четыре|пять|с\s+весом|вес|на\s+\d+)\b|\d+(?:[.,]\d+)?\s*кг",
        name_part,
        maxsplit=1,
        flags=re.IGNORECASE
    )[0]
    exercise_name = name_part.strip(" ,.-—").capitalize()
    if len(exercise_name) < 3:
        return None

    entries = []

    # Вариант А: '4 по 30' или '3x12'
    multi_matches = re.findall(r"(\d+)\s*(?:подход[аов]*\s*)?(?:по|x|х|\*)\s*(\d+)", normalized)
    if multi_matches:
        for s_str, r_str in multi_matches:
            entries.append({"sets": int(s_str), "reps": int(r_str), "weight": weight})

    # Вариант Б: '3 16, 4 20' или '3 подход на 24'
    ord_matches = re.findall(r"(?:^|[,.;]\s*)([1-9])\s*(?:подход[ае]?\s*)?(?:на\s+|[-—:]\s*)?(\d{1,3})(?=\s*(?:[,.;]|повтор|раз|$))", normalized)
    for _, r_str in ord_matches:
        reps_val = int(r_str)
        if not any(e["reps"] == reps_val and e["sets"] == 1 for e in entries):
            entries.append({"sets": 1, "reps": reps_val, "weight": weight})

    # Вариант В: перечисление после двоеточия ': 14, 14, 14, 16'
    if not entries and ":" in normalized:
        after_colon = normalized.split(":", 1)[1]
        nums = [int(n) for n in re.findall(r"\b\d{1,3}\b", after_colon)]
        for r_val in nums:
            entries.append({"sets": 1, "reps": r_val, "weight": weight})

    # Вариант Г: одиночный подход 'на 18', '18 повторений', '15 раз'
    if not entries:
        single_match = re.search(r"(?:на\s+)?(\d{1,3})\s*(?:повтор\w*|раз\b)|(?:сделал|пожал|присел|подтянулся|на)\s+(\d{1,3})\b", normalized)
        if single_match:
            r_val = int(single_match.group(1) or single_match.group(2))
            if 1 <= r_val <= 200:
                entries.append({"sets": 1, "reps": r_val, "weight": weight})

    if not entries:
        return None

    total_sets = sum(e["sets"] for e in entries)
    total_reps = sum(e["sets"] * e["reps"] for e in entries)
    total_tonnage = round(total_reps * weight, 1)

    return {
        "exercise_name": exercise_name,
        "entries": entries,
        "summary": {
            "total_sets": total_sets,
            "total_reps": total_reps,
            "weight_kg": weight,
            "tonnage_kg": total_tonnage
        }
    }
