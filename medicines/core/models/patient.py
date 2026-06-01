from django.db import models
from django.utils import timezone
from .abstracts import UpdatableAbstractModel

class Patient(UpdatableAbstractModel):
    class Gender(models.TextChoices):
        MALE = 'male', 'Male'
        FEMALE = 'female', 'Female'
        OTHER = 'other', 'Other'

    name = models.CharField(max_length=150)
    image = models.ImageField(upload_to='patients/', blank=True, null=True)
    phone = models.CharField(max_length=30, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True)
    address = models.CharField(max_length=300, blank=True)
    allergy_notes = models.TextField(blank=True)

    class Meta:
        db_table = 'patients'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def age(self):
        if self.date_of_birth:
            today = timezone.now().date()
            return today.year - self.date_of_birth.year  - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        return None