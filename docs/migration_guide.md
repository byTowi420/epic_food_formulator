# UI Integration Migration Guide

## Overview

This guide explains how to integrate the Clean Architecture (presenters + use cases) with the existing MainWindow UI.

## Current State

**Before:**
```
MainWindow (4554 lines)
  └─> services/usda_api.py (direct calls)
  └─> services/nutrient_normalizer.py (direct calls)
  └─> Business logic embedded in UI methods
```

**After (Target):**
```
MainWindow (<500 lines, coordinator only)
  └─> FormulationPresenter
        └─> Use Cases
              └─> Domain Services
  └─> SearchPresenter
        └─> Use Cases
              └─> Infrastructure
```

---

## Migration Strategy

### Option 1: Gradual Migration (Recommended)

Migrate one feature at a time while keeping the app functional.

#### Step 1: Add Presenters to MainWindow

```python
# In ui/main_window.py

from ui.presenters.formulation_presenter import FormulationPresenter
from ui.presenters.search_presenter import SearchPresenter

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Add presenters
        self.formulation_presenter = FormulationPresenter()
        self.search_presenter = SearchPresenter()

        # ... rest of initialization
```

#### Step 2: Migrate Search Feature

Replace old search code with presenter:

```python
# BEFORE (old code):
def on_search_button_clicked(self):
    query = self.search_input.text()
    from services.usda_api import search_foods
    results = search_foods(query, page_size=25)
    self._populate_search_results(results)

# AFTER (using presenter):
def on_search_button_clicked(self):
    query = self.search_input.text()
    results = self.search_presenter.search(
        query,
        page_size=25,
        include_branded=self.include_branded_checkbox.isChecked()
    )
    self._populate_search_results(results)
```

#### Step 3: Migrate Add Ingredient

```python
# BEFORE:
def on_add_ingredient_clicked(self):
    fdc_id = self.selected_food_id
    from services.usda_api import get_food_details
    details = get_food_details(fdc_id)
    # ... normalize, create item dict, add to self.formulation_items
    self._refresh_tables()

# AFTER:
def on_add_ingredient_clicked(self):
    fdc_id = self.selected_food_id
    ui_item = self.formulation_presenter.add_ingredient(
        fdc_id=fdc_id,
        amount_g=100.0
    )
    self._add_ui_item_to_table(ui_item)
    self._refresh_totals()
```

#### Step 4: Migrate Calculate Totals

```python
# BEFORE:
def _calculate_totals(self):
    # 50+ lines of calculation logic
    totals = {}
    for item in self.formulation_items:
        # ... complex calculation
    return totals

# AFTER:
def _calculate_totals(self):
    return self.formulation_presenter.calculate_totals()
```

#### Step 5: Migrate Save/Load

```python
# BEFORE:
def save_formulation(self, filename):
    data = {
        "name": self.formulation_name,
        "ingredients": self.formulation_items
    }
    with open(filename, 'w') as f:
        json.dump(data, f)

# AFTER:
def save_formulation(self, filename):
    self.formulation_presenter.save_to_file(filename)
```

---

### Option 2: Clean Slate (Advanced)

Create new MainWindow from scratch using presenters.

See `docs/ui_refactor_example.md` for a simplified example.

---

## Data Flow Examples

### Adding an Ingredient

**Old Way:**
```
User clicks "Add"
  → MainWindow.on_add_clicked()
    → services.usda_api.get_food_details()
    → services.nutrient_normalizer.normalize_nutrients()
    → Create dict manually
    → self.formulation_items.append(dict)
    → self._refresh_tables() (recalculates everything)
```

**New Way:**
```
User clicks "Add"
  → MainWindow.on_add_clicked()
    → formulation_presenter.add_ingredient(fdc_id, amount)
      → AddIngredientUseCase.execute()
        → USDAFoodRepository.get_by_id()
        → normalize_nutrients()
        → Domain Formulation.add_ingredient()
      → Returns UI item dict
    → MainWindow updates table with UI item
    → MainWindow.refresh_totals()
      → formulation_presenter.calculate_totals()
```

### Calculating Totals

**Old Way:**
```
_calculate_totals():
  50 lines of calculation logic
  Loops through self.formulation_items
  Handles scaling, normalization
  Returns dict
```

**New Way:**
```
_calculate_totals():
  return self.formulation_presenter.calculate_totals()
```

All calculation logic is in NutrientCalculator (tested).

---

## State Management

### Old Approach

State scattered across MainWindow:
```python
self.formulation_items = []  # List of dicts
self.formulation_name = "..."
self.quantity_mode = "g"
# ... 50+ other attributes
```

### New Approach

State in Presenter:
```python
# In MainWindow:
self.formulation_presenter = FormulationPresenter()

# State managed by presenter:
self.formulation_presenter.formulation_name
self.formulation_presenter.get_ui_items()  # Returns formatted list
self.formulation_presenter.get_total_weight()
```

MainWindow only maintains UI-specific state (scroll position, selected row, etc.).

---

## Benefits of Migration

### Before
- ❌ 4554 lines in one file
- ❌ Business logic mixed with UI
- ❌ Impossible to test without running UI
- ❌ Hard to understand data flow

### After
- ✅ UI is thin coordinator (<500 lines)
- ✅ Business logic in tested domain services
- ✅ Clear separation of concerns
- ✅ Easy to add features (add use case, update presenter, call from UI)

---

## Testing Strategy

### Old Code
```python
# Can't test this without Qt:
def test_add_ingredient():
    window = MainWindow()
    window.show()
    # ... click buttons, check table state
```

### New Code
```python
# Test presenter without Qt:
def test_add_ingredient():
    presenter = FormulationPresenter()
    ui_item = presenter.add_ingredient(fdc_id=123, amount_g=100)
    assert ui_item["amount_g"] == 100
    assert presenter.get_ingredient_count() == 1
```

---

## Rollback Strategy

If something goes wrong:

1. **Gradual Migration**: Just don't use presenter for that feature yet
2. **Clean Slate**: Change `main.py` back to import old `MainWindow`

```python
# main.py - Toggle between old and new:

# Old:
# from ui.main_window import MainWindow

# New:
from ui.main_window_refactored import MainWindow
```

---

## Next Steps

1. **Start with Search** - Easiest to migrate, low risk
2. **Then Add Ingredient** - Core feature
3. **Then Calculations** - Removes most business logic
4. **Finally Save/Load/Export** - Polish

Each step can be validated independently.

---

## Example: Complete Search Migration

### Before
```python
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # ... 100 lines of setup

    def on_search_clicked(self):
        query = self.search_input.text()

        # Direct API call
        from services.usda_api import search_foods
        results = search_foods(
            query,
            page_size=self.page_size_spinbox.value()
        )

        # Populate results
        self.search_results_list.clear()
        for r in results:
            item = QListWidgetItem(r['description'])
            item.setData(Qt.UserRole, r['fdcId'])
            self.search_results_list.addItem(item)
```

### After
```python
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.search_presenter = SearchPresenter()  # ← Added
        # ... rest of setup

    def on_search_clicked(self):
        query = self.search_input.text()

        # Use presenter
        results = self.search_presenter.search(
            query,
            page_size=self.page_size_spinbox.value(),
            include_branded=self.include_branded_checkbox.isChecked()
        )

        # Populate results (same as before)
        self.search_results_list.clear()
        for r in results:
            item = QListWidgetItem(r['description'])
            item.setData(Qt.UserRole, r['fdcId'])
            self.search_results_list.addItem(item)
```

**Changes:**
- Added 1 line: `self.search_presenter = SearchPresenter()`
- Changed 1 line: Use presenter instead of direct API call
- Rest of UI code unchanged

**Benefits:**
- Search logic now tested
- Can swap USDA API implementation
- Caching handled transparently
- No UI changes visible to user

---

## FAQs

**Q: Do I have to migrate everything at once?**
A: No! Migrate one feature at a time. Old and new code can coexist.

**Q: Will this break my saved formulations?**
A: No. The presenters use the same JSON format.

**Q: Can I still use the old code?**
A: Yes. Keep `ui/main_window.py` as fallback. New code is in presenters.

**Q: How do I test my changes?**
A: Run `pytest` for unit/integration tests. Run `python main.py` to test UI.

**Q: What if I find a bug?**
A: File an issue or fix in presenter/use case. Tests will prevent regressions.

---

## Summary

**Migration is incremental and safe:**

1. Add presenters to MainWindow (`__init__`)
2. Replace one feature at a time
3. Test each feature after migration
4. Keep old code as fallback

**Result: Clean, maintainable, testable code.**
