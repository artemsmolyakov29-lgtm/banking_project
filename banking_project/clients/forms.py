from django import forms
from .models import Client


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = [
            'last_name', 'first_name', 'middle_name', 'birth_date', 'inn',
            'email', 'phone_number', 'address', 'actual_address',
            'passport_number', 'passport_issued_by', 'passport_issue_date',
            'credit_rating', 'is_vip', 'is_active'
        ]
        widgets = {
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите фамилию'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите имя'}),
            'middle_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите отчество'}),
            'birth_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'inn': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите ИНН'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'example@email.com'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+7 (XXX) XXX-XX-XX'}),
            'address': forms.Textarea(
                attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Введите адрес регистрации'}),
            'actual_address': forms.Textarea(
                attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Введите фактический адрес'}),
            'passport_number': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'Серия и номер паспорта'}),
            'passport_issued_by': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Кем выдан паспорт'}),
            'passport_issue_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'credit_rating': forms.NumberInput(attrs={'min': 0, 'max': 100, 'class': 'form-control'}),
            'is_vip': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Устанавливаем placeholder для полей, если они не установлены в widgets
        for field_name, field in self.fields.items():
            if hasattr(field, 'widget') and hasattr(field.widget, 'attrs'):
                if 'placeholder' not in field.widget.attrs:
                    field.widget.attrs['placeholder'] = f'Введите {field.label.lower()}'

    def clean_inn(self):
        inn = self.cleaned_data.get('inn')
        if inn and len(inn) not in [10, 12]:
            raise forms.ValidationError("ИНН должен содержать 10 или 12 цифр")
        return inn

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        # Базовая валидация номера телефона
        if phone_number and not phone_number.replace('+', '').replace(' ', '').replace('-', '').replace('(',
                                                                                                        '').replace(')',
                                                                                                                    '').isdigit():
            raise forms.ValidationError("Введите корректный номер телефона")
        return phone_number