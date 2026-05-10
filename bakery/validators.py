from django.core.exceptions import ValidationError


class ComplexPasswordValidator:
    def validate(self, password, user=None):
        errors = []
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if not any(character.isupper() for character in password):
            errors.append("Password must contain an uppercase letter.")
        if not any(character.islower() for character in password):
            errors.append("Password must contain a lowercase letter.")
        if not any(character.isdigit() for character in password):
            errors.append("Password must contain a number.")
        if not any(not character.isalnum() for character in password):
            errors.append("Password must contain a special character.")
        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return "Your password must contain uppercase and lowercase letters, a number, a special character, and at least 8 characters."
