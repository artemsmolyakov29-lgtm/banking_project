from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.apps import apps

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'})
    )
    full_name = forms.CharField(
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Полное имя'})
    )
    phone = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Телефон'})
    )
    passport_data = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Серия и номер паспорта'})
    )

    class Meta:
        model = apps.get_model('users', 'User')
        fields = ['username', 'email', 'phone', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Имя пользователя'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Добавляем Bootstrap классы ко всем полям
        for field_name, field in self.fields.items():
            if field_name not in ['username', 'email']:
                field.widget.attrs['class'] = 'form-control'

    def save(self, commit=True):
        User = apps.get_model('users', 'User')
        Client = apps.get_model('clients', 'Client')

        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.phone = self.cleaned_data['phone']

        if commit:
            user.save()
            # Создаем клиента при регистрации
            Client.objects.create(
                user=user,
                full_name=self.cleaned_data['full_name'],
                passport_data=self.cleaned_data['passport_data']
            )
        return user


class UserLoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Имя пользователя или Email'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Пароль'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Убираем стандартные метки
        self.fields['username'].label = ''
        self.fields['password'].label = ''