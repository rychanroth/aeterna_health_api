from django.db import models
from django.core.exceptions import ValidationError
from .abstracts import UpdatableAbstractModel

class Category(UpdatableAbstractModel):
    name = models.CharField(max_length=200)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    parent = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name = 'children' 
    )
    product_type = models.ForeignKey(
        'ProductType',
        on_delete=models.CASCADE,
        related_name='categories',
        verbose_name='product type'
    )

    class Meta:
        db_table = 'categories'
        verbose_name_plural = 'Categories' 
        ordering = ['name']
        constraints = [ 
            models.UniqueConstraint(
                fields=['name', 'product_type'],
                name='unique_category_per_product_type'
            )
        ]

    def __str__(self):
        return self.name

    @property
    def full_path(self):
        if self.parent:
            return f"{self.parent.full_path} > {self.name}"
        return f"{self.product_type.name} > {self.name}"

    @property
    def depth(self):
        if not self.parent_id:
            return 0
        if self.parent_id == self.pk:
            return 1
        return self.parent.depth + 1

    def get_ancestors(self):
        ancestors = []
        current = self.parent
        while current:
            ancestors.append(current)
            current = current.parent
        return ancestors

    def get_descendants(self):
        descendants = []
        for child in self.children.all():
            descendants.append(child)
            descendants.extend(child.get_descendants())
        return descendants

    def is_ancestor_of(self, category):
        return self in category.get_ancestors()

    def is_descendant_of(self, category):
        return category in self.get_ancestors()

    def clean(self):
        if self.parent_id is not None and self.parent_id == self.pk:
            raise ValidationError({'parent': 'Category cannot be its own parent.'})

        if self.parent_id:
            parent = self.parent if self.parent_id == getattr(self.parent, 'pk', None) else Category.objects.get(pk=self.parent_id)
            if parent.product_type_id != self.product_type_id:
                raise ValidationError({
                    'parent': f'Parent must belong to same ProductType.'
                })
            descendants = self.get_descendants() if self.pk else []
            if parent in descendants:
                raise ValidationError({'parent': 'Circular reference detected.'})

        if self.depth > 5:
            raise ValidationError({'parent': 'Maximum depth (5) exceeded.'})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def get_all_products(self):
        from django.db.models import Q
        from .product import Product # Local import to avoid circularity at load time
        
        category_ids = [self.id]
        for descendant in self.get_descendants():
            category_ids.append(descendant.id)
        return Product.objects.filter(category_id__in=category_ids)

    def get_total_stock(self):
        return self.get_all_products().aggregate(
            total=models.Sum('stock_quantity')
        )['total'] or 0

    def get_total_value(self):
        from django.db.models import F
        return self.get_all_products().aggregate(
            total=models.Sum(models.F('stock_quantity') * models.F('selling_price'))
        )['total'] or 0