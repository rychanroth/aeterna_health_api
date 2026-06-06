from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from .abstracts import UpdatableAbstractModel

class Product(UpdatableAbstractModel):
    class BaseUnit(models.TextChoices):
        TABLET = 'tablet', 'Tablet'
        CAPSULE = 'capsule', 'Capsule'
        SYRUP = 'syrup', 'Syrup'
        ML = 'ml', 'Milliliter (mL)'
        G = 'g', 'Gram (g)'
        MG = 'mg', 'Milligram (mg)'
        VIAL = 'vial', 'Vial'
        AMPOULE = 'ampoule', 'Ampoule'
        TUBE = 'tube', 'Tube'
        BOTTLE = 'bottle', 'Bottle'
        PIECE = 'piece', 'Piece'
        PACK = 'pack', 'Pack'
        ROLL = 'roll', 'Roll'
        BOX = 'box', 'Box'
        SET = 'set', 'Set'
        DIAPER = 'diaper', 'Diaper'
        WIPES = 'wipes', 'Wipes'
        SACHET = 'sachet', 'Sachet'
        UNIT = 'unit', 'Unit'

        @classmethod
        def get_medicine_units(cls):
            return [cls.TABLET, cls.CAPSULE, cls.SYRUP, cls.ML, cls.G,
                    cls.MG, cls.VIAL, cls.AMPOULE, cls.TUBE, cls.BOTTLE]

        @classmethod
        def get_equipment_units(cls):
            return [cls.PIECE, cls.PACK, cls.ROLL, cls.BOX, cls.SET]

        @classmethod
        def get_consumable_units(cls):
            return [cls.DIAPER, cls.WIPES, cls.SACHET, cls.PIECE, cls.PACK]

    name = models.CharField(max_length=200)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    product_type = models.ForeignKey('ProductType', on_delete=models.RESTRICT, null=True, blank=True, related_name='products')
    base_unit = models.CharField(max_length=20, choices=BaseUnit.choices, default=BaseUnit.TABLET)
    category = models.ForeignKey('Category', on_delete=models.RESTRICT, null=True, blank=True, related_name='products')
    description = models.TextField(blank=True)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    requires_prescription = models.BooleanField(default=False)

    class Meta:
        db_table = 'products'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    # FIX: DELETED properties, because it's moved to database-level annotations in the ViewSet

    @property
    def effective_requires_prescription(self):
        if not self.product_type:
            return self.requires_prescription
        return self.requires_prescription or self.product_type.requires_prescription

    def clean(self):
        super().clean()
        # Removed stock_quantity and expiration validation from here
        if self.product_type and self.product_type.requires_expiration and self.requires_prescription and not self.requires_prescription:
            pass # Logic can be refined if needed

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)