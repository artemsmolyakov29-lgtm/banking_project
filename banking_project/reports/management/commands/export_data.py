from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.apps import apps
from django.http import HttpResponse
import csv
import json
from datetime import datetime
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Экспорт данных через командную строку'

    def add_arguments(self, parser):
        parser.add_argument(
            'data_type',
            type=str,
            choices=['clients', 'credits', 'deposits', 'transactions', 'cards'],
            help='Тип данных для экспорта',
        )
        parser.add_argument(
            'format',
            type=str,
            choices=['json', 'csv', 'xlsx'],
            help='Формат экспорта',
        )
        parser.add_argument(
            '--output',
            type=str,
            help='Путь для сохранения файла (если не указан, выводится в stdout)',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='ID пользователя, от имени которого выполняется экспорт',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=1000,
            help='Ограничение количества записей (по умолчанию: 1000)',
        )
        parser.add_argument(
            '--include-metadata',
            action='store_true',
            help='Включать метаданные в экспорт',
        )

    def get_data_processor(self):
        """Ленивая загрузка DataProcessor"""
        try:
            from ...utils import DataProcessor
            return DataProcessor
        except ImportError as e:
            logger.error(f"Ошибка импорта DataProcessor: {e}")

            # Создаем базовую реализацию если импорт не удался
            class StubDataProcessor:
                @staticmethod
                def prepare_client_data(queryset):
                    data = []
                    for client in queryset:
                        data.append({
                            'id': client.id,
                            'full_name': getattr(client, 'full_name', ''),
                            'inn': getattr(client, 'inn', ''),
                        })
                    return data

                @staticmethod
                def prepare_credit_data(queryset):
                    data = []
                    for credit in queryset:
                        data.append({
                            'id': credit.id,
                            'client_name': getattr(credit.client, 'full_name', '') if credit.client else '',
                            'amount': str(getattr(credit, 'amount', '0')),
                        })
                    return data

                @staticmethod
                def prepare_deposit_data(queryset):
                    data = []
                    for deposit in queryset:
                        data.append({
                            'id': deposit.id,
                            'client_name': getattr(deposit.client, 'full_name', '') if deposit.client else '',
                            'amount': str(getattr(deposit, 'amount', '0')),
                        })
                    return data

                @staticmethod
                def prepare_transaction_data(queryset):
                    data = []
                    for transaction in queryset:
                        data.append({
                            'id': transaction.id,
                            'amount': str(getattr(transaction, 'amount', '0')),
                            'transaction_type': getattr(transaction, 'transaction_type', ''),
                        })
                    return data

                @staticmethod
                def prepare_card_data(queryset):
                    data = []
                    for card in queryset:
                        data.append({
                            'id': card.id,
                            'cardholder_name': getattr(card, 'cardholder_name', ''),
                            'card_type': getattr(card, 'card_type', ''),
                        })
                    return data

            return StubDataProcessor

    def export_to_json(self, data, include_metadata=False):
        """Экспорт данных в JSON"""
        if include_metadata:
            export_data = {
                'metadata': {
                    'export_date': datetime.now().isoformat(),
                    'record_count': len(data),
                    'version': '1.0'
                },
                'data': data
            }
        else:
            export_data = data

        response = HttpResponse(
            json.dumps(export_data, ensure_ascii=False, indent=2),
            content_type='application/json; charset=utf-8'
        )
        return response

    def export_to_csv(self, data, include_metadata=False):
        """Экспорт данных в CSV"""
        if not data:
            return None

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response.write('\ufeff')  # BOM для корректного отображения кириллицы в Excel

        writer = csv.writer(response)

        # Заголовки
        headers = list(data[0].keys())
        writer.writerow(headers)

        # Данные
        for item in data:
            row = []
            for key in headers:
                value = item.get(key, '')
                # Преобразуем Decimal в строку
                if isinstance(value, Decimal):
                    value = str(value)
                # Преобразуем даты в строки
                elif isinstance(value, datetime):
                    value = value.strftime('%Y-%m-%d %H:%M:%S')
                row.append(value)
            writer.writerow(row)

        if include_metadata:
            writer.writerow([])
            writer.writerow(['# Metadata'])
            writer.writerow(['# Export Date:', datetime.now().isoformat()])
            writer.writerow(['# Record Count:', len(data)])

        return response

    def export_to_xlsx(self, data, include_metadata=False):
        """Экспорт данных в Excel (XLSX) - используем CSV с расширением xlsx"""
        response = self.export_to_csv(data, include_metadata)
        if response:
            response['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        return response

    def handle(self, *args, **options):
        data_type = options['data_type']
        export_format = options['format']
        output_path = options['output']
        user_id = options['user_id']
        limit = options['limit']
        include_metadata = options['include_metadata']

        DataProcessor = self.get_data_processor()

        self.stdout.write(
            self.style.SUCCESS(
                f"Начало экспорта {data_type} в формате {export_format}"
            )
        )

        # Получение пользователя
        User = get_user_model()
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"Пользователь с ID {user_id} не найден")
                )
                return
        else:
            # Используем первого суперпользователя
            user = User.objects.filter(is_superuser=True).first()
            if not user:
                self.stdout.write(
                    self.style.ERROR("Не найден суперпользователь для выполнения экспорта")
                )
                return

        # Получение данных
        try:
            data = self.get_data(data_type, limit, DataProcessor)
            if not data:
                self.stdout.write(
                    self.style.WARNING("Нет данных для экспорта")
                )
                return

            self.stdout.write(
                self.style.SUCCESS(f"Получено записей: {len(data)}")
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Ошибка при получении данных: {str(e)}")
            )
            return

        # Экспорт данных
        try:
            if export_format == 'json':
                result = self.export_to_json(data, include_metadata=include_metadata)
            elif export_format == 'csv':
                result = self.export_to_csv(data, include_metadata=include_metadata)
            elif export_format == 'xlsx':
                result = self.export_to_xlsx(data, include_metadata=include_metadata)
            else:
                self.stdout.write(
                    self.style.ERROR(f"Неподдерживаемый формат: {export_format}")
                )
                return

            if not result:
                self.stdout.write(
                    self.style.ERROR("Ошибка при создании файла экспорта")
                )
                return

            if output_path:
                # Сохранение в файл
                with open(output_path, 'wb') as f:
                    f.write(result.content)
                self.stdout.write(
                    self.style.SUCCESS(f"Данные сохранены в: {output_path}")
                )
            else:
                # Вывод в stdout
                self.stdout.write(result.content.decode('utf-8'))

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Ошибка при экспорте данных: {str(e)}")
            )
            return

    def get_data(self, data_type, limit, DataProcessor):
        """Получение данных для экспорта"""

        if data_type == 'clients':
            Client = apps.get_model('clients', 'Client')
            queryset = Client.objects.all()[:limit]
            return DataProcessor.prepare_client_data(queryset)

        elif data_type == 'credits':
            Credit = apps.get_model('credits', 'Credit')
            queryset = Credit.objects.all()[:limit]
            return DataProcessor.prepare_credit_data(queryset)

        elif data_type == 'deposits':
            Deposit = apps.get_model('deposits', 'Deposit')
            queryset = Deposit.objects.all()[:limit]
            return DataProcessor.prepare_deposit_data(queryset)

        elif data_type == 'transactions':
            Transaction = apps.get_model('transactions', 'Transaction')
            queryset = Transaction.objects.all()[:limit]
            return DataProcessor.prepare_transaction_data(queryset)

        elif data_type == 'cards':
            Card = apps.get_model('cards', 'Card')
            queryset = Card.objects.all()[:limit]
            return DataProcessor.prepare_card_data(queryset)

        return []