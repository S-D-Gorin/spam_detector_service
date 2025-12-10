import re

RU_PHONE_PATTERN = re.compile(
    r"(?:\+7|8|7)\s?(?:\(?\d{3}\)?|\d{3})[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}"
)

KZ_PHONE_PATTERN = re.compile(
    r"\+7\s?(?:\(7\d{2}\)|7\d{2})[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}"
)

UZ_PHONE_PATTERN = re.compile(
    r"\+998\s?(?:\(?\d{2}\)?|\d{2})[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}"
)

BL_PHONE_PATTERN = re.compile(
    r"\+375\s?(?:\(?\d{2}\)?|\d{2})[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}"
)

country_phone_patterns = {
    'ru': RU_PHONE_PATTERN,
    'kz': KZ_PHONE_PATTERN,
    'uz': UZ_PHONE_PATTERN,
    'bl': BL_PHONE_PATTERN,
}

class PhoneService:
    def __init__(self, text, params):
        self.text = text
        # self.params = params
        self.country = params.get('country', 'ru')

    # -----------------------------------------------------------
    def get_phones_from_text_by_country(self, country=None):
        """
        Если country указан — ищем только по его паттерну.
        Если country=None — ищем по всем странам.
        """
        phones = []

        # Если страна указана явно — используем только её
        if country:
            pattern = country_phone_patterns.get(country, RU_PHONE_PATTERN)
            return re.findall(pattern, self.text)

        # Если страна не указана → ищем по всем паттернам
        for c, pattern in country_phone_patterns.items():
            matches = re.findall(pattern, self.text)
            phones.extend(matches)

        return phones


    # -----------------------------------------------------------
    @staticmethod
    def normalize_phone(phone: str) -> str | None:
        """Приводит номер телефона к международному формату."""
        if not phone:
            return None

        digits = re.sub(r"\D", "", phone)

        # РФ/КЗ
        if len(digits) == 11 and digits.startswith("8"):
            return "+7" + digits[1:]

        if len(digits) == 11 and digits.startswith("7"):
            return "+7" + digits[1:]

        if len(digits) == 11 and digits.startswith("87"):  # Казахстан
            return "+7" + digits[1:]

        # Узбекистан
        if digits.startswith("998") and len(digits) == 12:
            return "+" + digits

        # Беларусь
        if digits.startswith("375") and len(digits) == 12:
            return "+" + digits

        return None

    # -----------------------------------------------------------
    @staticmethod
    def is_fake_phone(phone: str) -> bool:
        """Определяет поддельный номер."""
        if not phone:
            return True

        digits = re.sub(r"\D", "", phone)
        if not digits:
            return True

        # Определяем страну
        country = None
        local_part = None

        if len(digits) == 11 and digits[0] in ("7", "8"):
            if digits[0] == "8":
                digits = "7" + digits[1:]
            country = "ru_kz"
            local_part = digits[1:]

        elif len(digits) == 12 and digits.startswith("998"):
            country = "uz"
            local_part = digits[3:]

        elif len(digits) == 12 and digits.startswith("375"):
            country = "by"
            local_part = digits[3:]

        else:
            return True

        # Все цифры одинаковые
        if len(set(local_part)) == 1:
            return True

        # Только 1–2 разных цифры
        if len(local_part) >= 7 and len(set(local_part)) <= 2:
            return True

        # Почти весь номер из 0 или 9
        if local_part.count("9") >= len(local_part) - 1:
            return True
        if local_part.count("0") >= len(local_part) - 1:
            return True

        return False

    # -----------------------------------------------------------
    def analyze(self):
        result = {}

        for country_code, pattern in country_phone_patterns.items():
            # --- 1. Ищем телефоны конкретной страны ---
            raw = re.findall(pattern, self.text)

            # Если нет ни одного номера — пропускаем страну
            if not raw:
                continue

            normalized = []
            valid = []
            fake = []

            for phone in raw:
                norm = self.normalize_phone(phone)

                # Если не нормализуется — фейк
                if not norm:
                    fake.append(phone)
                    continue

                if self.is_fake_phone(norm):
                    fake.append(norm)
                else:
                    valid.append(norm)

                normalized.append(norm)

            # --- 2. Добавляем в результат только если НЕ пусто ---
            result[country_code] = {
                "phones_raw": raw,
                "phones_normalized": normalized,
                "valid": valid,
                "fake": fake,
                "count_valid": len(valid),
                "count_fake": len(fake),
                "count_total": len(raw),
            }

        return result
