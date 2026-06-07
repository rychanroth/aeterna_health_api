from django.apps import AppConfig


class MedicinesCoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'medicines.core'
    label = 'medicines'  # CRITICAL: Tells Django this still owns the 'medicines' DB tables
    verbose_name = 'Medicines Core'

    def ready(self):
        import medicines.core.signals 