# Epic Food Formulator - Análisis del Proyecto y Estrategia de Refactorización

## 📋 Descripción del Proyecto

**Epic Food Formulator** es una aplicación de escritorio desarrollada en Python con PySide6 (Qt) que permite formular recetas alimentarias basándose en información nutricional de la base de datos FoodData Central del USDA (Departamento de Agricultura de Estados Unidos).

### Funcionalidades Principales

1. **Búsqueda de Alimentos**: Consulta la API de USDA para buscar alimentos por nombre, con filtros por tipo de datos (Foundation, SR Legacy, Survey, Branded, etc.)

2. **Formulación de Recetas**:
   - Agregar ingredientes a una formulación
   - Especificar cantidades en gramos o porcentajes
   - Bloquear proporciones de ingredientes
   - Calcular automáticamente valores nutricionales totales

3. **Visualización Nutricional**:
   - Tabla de ingredientes con cantidades
   - Tabla de nutrientes con valores por ingrediente y totales
   - Etiqueta nutricional estilo FDA/NLEA
   - Normalización inteligente de nutrientes (fusión de alias, cálculo de energía, etc.)

4. **Persistencia y Exportación**:
   - Guardar/cargar formulaciones en formato JSON
   - Exportar a Excel con formato profesional
   - Caché de búsquedas y detalles de alimentos

### Arquitectura Actual

```
epic_food_formulator/
├── main.py                          # Punto de entrada (19 líneas)
├── services/
│   ├── usda_api.py                  # Cliente API USDA (281 líneas)
│   └── nutrient_normalizer.py      # Normalización de nutrientes (392 líneas)
├── ui/
│   ├── main_window.py               # Ventana principal (4554 líneas ⚠️)
│   └── workers.py                   # Workers para threads (148 líneas)
├── saves/                           # Formulaciones guardadas (JSON)
└── requirements.txt                 # Dependencias
```

### Dependencias

- **PySide6**: Framework Qt para interfaces gráficas
- **requests**: Cliente HTTP para API REST
- **python-dotenv**: Gestión de variables de entorno
- **pandas**: Procesamiento de datos tabulares
- **openpyxl**: Exportación a Excel

---

## 🔍 Análisis de Clean Code - Problemas Identificados

### 1. **Violación Crítica del Principio de Responsabilidad Única (SRP)**

**Problema**: `ui/main_window.py` tiene **4554 líneas** y maneja múltiples responsabilidades:
- Interfaz gráfica (widgets, layouts)
- Lógica de negocio (cálculos nutricionales, formulación)
- Gestión de estado (formulation_items, caché)
- Manejo de archivos (JSON, Excel)
- Comunicación con API
- Normalización de datos
- Generación de etiquetas nutricionales

**Consecuencias**:
- Código imposible de mantener
- Testing extremadamente difícil
- Alto acoplamiento
- Duplicación de lógica
- Cambios en un área afectan otras áreas

### 2. **Falta de Separación entre Lógica de Negocio y Presentación**

**Problema**: Cálculos nutricionales, validaciones y transformaciones de datos están embebidos directamente en métodos de la clase `MainWindow`.

**Ejemplo**: Métodos como `_calculate_totals()`, `_refresh_label_table()`, `_build_nutrient_catalog()` mezclan lógica de negocio con actualización de UI.

### 3. **Ausencia de Tests**

**Problema**: No existe ningún archivo de test (`test_*.py`, `*_test.py`).

**Riesgos**:
- Refactorización peligrosa (sin red de seguridad)
- Bugs difíciles de reproducir
- Regresiones no detectadas

### 4. **Gestión de Estado Global y Mutable**

**Problema**:
- Variables globales con locks en `usda_api.py` (`_session`, `_details_cache`, `_search_cache`)
- Estado distribuido en múltiples atributos de `MainWindow` sin encapsulación

**Problemas**:
- Threading bugs potenciales
- Difícil rastrear cambios de estado
- Imposible tener múltiples instancias independientes

### 5. **Nomenclatura Inconsistente**

**Problema**: Mezcla de español e inglés:
- Inglés: `formulation_items`, `nutrient_normalizer`, `search_foods`
- Español: `"No se pudo cargar"`, `"Lentejas y Oreos.json"`

**Impacto**: Dificulta lectura y colaboración internacional.

### 6. **Magic Numbers y Strings**

**Ejemplos**:
```python
self.import_read_timeout = 8.0
self.search_fetch_page_size = 200
DEFAULT_TIMEOUT = (3.05, 20)
self._fat_row_role = Qt.UserRole + 501
```

**Problema**: Números y strings hardcodeados sin constantes con nombres descriptivos.

### 7. **Manejo de Excepciones Genérico**

**Ejemplo**:
```python
except Exception as exc:  # noqa: BLE001
    self.error.emit(str(exc))
```

**Problema**: Captura de `Exception` oculta bugs reales (KeyError, TypeError, etc.).

### 8. **Complejidad Ciclomática Alta**

**Problema**: Métodos extremadamente largos (100-300+ líneas) con múltiples niveles de anidación.

**Ejemplo**: Métodos en `main_window.py` para renderizado de tablas, cálculos, exportación.

### 9. **Acoplamiento Fuerte**

**Problema**: `MainWindow` conoce detalles de implementación de:
- API USDA (IDs, formatos, timeouts)
- Estructura de JSON
- Formato de Excel
- Normalización de nutrientes

### 10. **Falta de Documentación**

**Problema**:
- No hay docstrings en muchas funciones
- No hay documentación de arquitectura
- README.md vacío (solo título)

---

## 🏗️ Estrategia de Refactorización - Clean Code

### Principios Guía

1. **SOLID Principles**
2. **DRY (Don't Repeat Yourself)**
3. **YAGNI (You Aren't Gonna Need It)**
4. **Separation of Concerns**
5. **Test-Driven Development (TDD)**

---

## 📐 Arquitectura Propuesta

### Estructura de Directorios (Clean Architecture)

```
epic_food_formulator/
├── main.py                          # Entry point (mínimo)
├── config/
│   ├── __init__.py
│   ├── settings.py                  # Configuración centralizada
│   └── constants.py                 # Constantes (timeouts, roles Qt, etc.)
├── domain/                          # Lógica de negocio pura
│   ├── __init__.py
│   ├── models.py                    # Food, Ingredient, Formulation, Nutrient
│   ├── value_objects.py             # Amount, Percentage, NutrientValue
│   ├── exceptions.py                # Custom exceptions
│   └── services/
│       ├── __init__.py
│       ├── formulation_service.py   # Lógica de formulación
│       ├── nutrient_calculator.py   # Cálculos nutricionales
│       └── label_generator.py       # Generación de etiquetas
├── infrastructure/                  # Implementaciones concretas
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── usda_client.py           # Cliente API (refactorizado)
│   │   └── cache.py                 # Caché abstracto
│   ├── persistence/
│   │   ├── __init__.py
│   │   ├── json_repository.py       # Save/Load JSON
│   │   └── excel_exporter.py        # Exportación Excel
│   └── normalizers/
│       ├── __init__.py
│       └── usda_normalizer.py       # Normalización USDA
├── application/                     # Casos de uso
│   ├── __init__.py
│   ├── search_foods.py              # UseCase: Buscar alimentos
│   ├── add_ingredient.py            # UseCase: Agregar ingrediente
│   ├── calculate_totals.py          # UseCase: Calcular totales
│   ├── export_formulation.py        # UseCase: Exportar
│   └── save_formulation.py          # UseCase: Guardar
├── ui/                              # Capa de presentación
│   ├── __init__.py
│   ├── main_window.py               # MainWindow (solo UI, <500 líneas)
│   ├── presenters/
│   │   ├── __init__.py
│   │   ├── formulation_presenter.py # Presenter pattern
│   │   └── search_presenter.py
│   ├── widgets/
│   │   ├── __init__.py
│   │   ├── ingredients_table.py     # Widget tabla ingredientes
│   │   ├── nutrients_table.py       # Widget tabla nutrientes
│   │   ├── label_widget.py          # Widget etiqueta nutricional
│   │   └── search_widget.py         # Widget búsqueda
│   ├── dialogs/
│   │   ├── __init__.py
│   │   └── add_ingredient_dialog.py
│   └── workers/
│       ├── __init__.py
│       └── api_worker.py            # Workers Qt (refactorizado)
├── tests/                           # Tests unitarios e integración
│   ├── __init__.py
│   ├── unit/
│   │   ├── test_models.py
│   │   ├── test_nutrient_calculator.py
│   │   ├── test_usda_normalizer.py
│   │   └── test_formulation_service.py
│   ├── integration/
│   │   ├── test_usda_client.py
│   │   └── test_excel_exporter.py
│   └── fixtures/
│       └── sample_foods.json
├── docs/                            # Documentación
│   ├── architecture.md
│   ├── api_usage.md
│   └── user_guide.md
├── .env.example
├── .gitignore
├── requirements.txt
├── requirements-dev.txt             # pytest, black, mypy, ruff
└── README.md                        # Documentación principal
```

---

## 🔧 Plan de Refactorización - Fases

### **FASE 1: Configuración y Testing Base (Prioridad: Alta)**

#### Objetivo
Establecer infraestructura de desarrollo y primeros tests.

#### Tareas

1. **Configuración de Desarrollo**
   ```bash
   # requirements-dev.txt
   pytest>=7.0.0
   pytest-cov>=4.0.0
   pytest-qt>=4.2.0
   black>=23.0.0
   ruff>=0.1.0
   mypy>=1.0.0
   ```

2. **Crear `config/constants.py`**
   - Extraer todos los magic numbers
   - Roles Qt, timeouts, tamaños de página

3. **Crear `domain/exceptions.py`**
   ```python
   class FoodFormulatorError(Exception):
       """Base exception"""

   class IngredientNotFoundError(FoodFormulatorError):
       """Ingredient not found in USDA API"""

   class InvalidFormulationError(FoodFormulatorError):
       """Invalid formulation state"""
   ```

4. **Escribir Tests de Caracterización**
   - Tests que documenten el comportamiento actual
   - Empezar con `nutrient_normalizer.py` (ya está aislado)

#### Resultado
✅ Red de seguridad para refactorización
✅ Configuración de desarrollo profesional

---

### **FASE 2: Extracción de Modelos del Dominio (Prioridad: Alta)**

#### Objetivo
Definir modelos de negocio inmutables y bien tipados.

#### Tareas

1. **Crear `domain/models.py`**
   ```python
   from dataclasses import dataclass, field
   from typing import Dict, List, Optional
   from decimal import Decimal

   @dataclass(frozen=True)
   class Nutrient:
       id: Optional[int]
       name: str
       unit: str
       amount: Decimal

   @dataclass(frozen=True)
   class Food:
       fdc_id: int
       description: str
       data_type: str
       brand_owner: str
       nutrients: List[Nutrient] = field(default_factory=list)

   @dataclass
   class Ingredient:
       food: Food
       amount_g: Decimal
       locked: bool = False

       @property
       def percentage(self) -> Decimal:
           # Calculado desde formulation
           pass

   @dataclass
   class Formulation:
       name: str
       ingredients: List[Ingredient] = field(default_factory=list)
       quantity_mode: str = "g"

       def total_weight(self) -> Decimal:
           return sum(ing.amount_g for ing in self.ingredients)
   ```

2. **Tests para Modelos**
   ```python
   # tests/unit/test_models.py
   def test_food_immutability():
       food = Food(fdc_id=123, description="Apple", ...)
       with pytest.raises(FrozenInstanceError):
           food.description = "Banana"
   ```

#### Resultado
✅ Modelos del dominio bien definidos
✅ Inmutabilidad y type safety

---

### **FASE 3: Extracción de Servicios del Dominio (Prioridad: Alta)**

#### Objetivo
Mover lógica de negocio fuera de `MainWindow`.

#### Tareas

1. **Crear `domain/services/nutrient_calculator.py`**
   ```python
   from decimal import Decimal
   from typing import List, Dict
   from domain.models import Formulation, Nutrient

   class NutrientCalculator:
       def calculate_totals(
           self,
           formulation: Formulation
       ) -> Dict[str, Decimal]:
           """Calcula totales nutricionales por 100g."""
           # Extraer lógica de _calculate_totals()
           pass

       def calculate_per_ingredient(
           self,
           formulation: Formulation
       ) -> Dict[int, Dict[str, Decimal]]:
           """Calcula nutrientes por ingrediente."""
           pass
   ```

2. **Crear `domain/services/formulation_service.py`**
   ```python
   class FormulationService:
       def add_ingredient(
           self,
           formulation: Formulation,
           food: Food,
           amount_g: Decimal
       ) -> Formulation:
           """Agrega ingrediente (inmutable)."""
           pass

       def remove_ingredient(
           self,
           formulation: Formulation,
           index: int
       ) -> Formulation:
           pass

       def adjust_locked_ingredients(
           self,
           formulation: Formulation
       ) -> Formulation:
           """Ajusta proporciones manteniendo locks."""
           pass
   ```

3. **Crear `domain/services/label_generator.py`**
   ```python
   from typing import List, Tuple

   class NutritionLabelGenerator:
       def generate_fda_label(
           self,
           nutrient_totals: Dict[str, Decimal],
           serving_size_g: Decimal
       ) -> List[Tuple[str, str, str]]:
           """Genera datos para etiqueta FDA/NLEA."""
           # Extraer lógica de _refresh_label_table()
           pass
   ```

4. **Tests Unitarios**
   ```python
   # tests/unit/test_nutrient_calculator.py
   def test_calculate_totals_simple_formulation():
       # Given
       formulation = create_sample_formulation()
       calculator = NutrientCalculator()

       # When
       totals = calculator.calculate_totals(formulation)

       # Then
       assert totals["Protein"] == Decimal("15.2")
   ```

#### Resultado
✅ Lógica de negocio testable e independiente de UI
✅ Servicios reutilizables

---

### **FASE 4: Refactorización de Infraestructura (Prioridad: Media)**

#### Objetivo
Mejorar cliente API y caché.

#### Tareas

1. **Refactorizar `infrastructure/api/usda_client.py`**
   ```python
   from abc import ABC, abstractmethod
   from typing import List, Optional

   class FoodRepository(ABC):
       @abstractmethod
       def search(self, query: str, page: int) -> List[Food]:
           pass

       @abstractmethod
       def get_by_id(self, fdc_id: int) -> Optional[Food]:
           pass

   class USDAFoodRepository(FoodRepository):
       def __init__(self, api_key: str, cache: Cache):
           self._api_key = api_key
           self._cache = cache
           self._session = self._create_session()

       def search(self, query: str, page: int) -> List[Food]:
           cache_key = f"search:{query}:{page}"
           if cached := self._cache.get(cache_key):
               return cached
           # ... lógica actual ...
   ```

2. **Crear `infrastructure/api/cache.py`**
   ```python
   from abc import ABC, abstractmethod
   from typing import Any, Optional

   class Cache(ABC):
       @abstractmethod
       def get(self, key: str) -> Optional[Any]:
           pass

       @abstractmethod
       def set(self, key: str, value: Any, ttl: int = 3600):
           pass

   class InMemoryCache(Cache):
       def __init__(self):
           self._store: Dict[str, Tuple[Any, float]] = {}
           self._lock = threading.Lock()

       # ... implementación ...
   ```

3. **Mover Normalización**
   - `services/nutrient_normalizer.py` → `infrastructure/normalizers/usda_normalizer.py`
   - Crear interfaz `Normalizer` abstracta

#### Resultado
✅ API desacoplada mediante abstracciones
✅ Caché reemplazable (testing, Redis, etc.)

---

### **FASE 5: Refactorización de UI (Prioridad: Media)**

#### Objetivo
Reducir `main_window.py` a coordinación pura de widgets.

#### Tareas

1. **Extraer Widgets Especializados**
   ```python
   # ui/widgets/ingredients_table.py
   class IngredientsTableWidget(QTableWidget):
       ingredient_changed = Signal(int, str, float)
       ingredient_removed = Signal(int)

       def __init__(self, parent=None):
           super().__init__(parent)
           self._setup_ui()

       def set_formulation(self, formulation: Formulation):
           self._populate_table(formulation)

       def _setup_ui(self):
           self.setColumnCount(5)
           # ... configuración ...
   ```

2. **Implementar Presenter Pattern**
   ```python
   # ui/presenters/formulation_presenter.py
   class FormulationPresenter:
       def __init__(
           self,
           view: 'MainWindow',
           formulation_service: FormulationService,
           calculator: NutrientCalculator
       ):
           self._view = view
           self._service = formulation_service
           self._calculator = calculator
           self._formulation = Formulation(name="New Formulation")

       def add_ingredient(self, food: Food, amount_g: float):
           self._formulation = self._service.add_ingredient(
               self._formulation, food, Decimal(amount_g)
           )
           self._update_view()

       def _update_view(self):
           totals = self._calculator.calculate_totals(self._formulation)
           self._view.update_ingredients(self._formulation)
           self._view.update_nutrients(totals)
   ```

3. **Refactorizar `main_window.py`**
   - Reducir a <500 líneas
   - Solo crear widgets y conectar señales
   - Delegar toda lógica al presenter

#### Resultado
✅ `MainWindow` limpio y mantenible
✅ Widgets reutilizables
✅ Lógica de presentación separada

---

### **FASE 6: Casos de Uso (Application Layer) (Prioridad: Media)**

#### Objetivo
Encapsular flujos de usuario complejos.

#### Tareas

1. **Crear Use Cases**
   ```python
   # application/export_formulation.py
   class ExportFormulationUseCase:
       def __init__(
           self,
           calculator: NutrientCalculator,
           exporter: ExcelExporter
       ):
           self._calculator = calculator
           self._exporter = exporter

       def execute(
           self,
           formulation: Formulation,
           output_path: Path
       ) -> None:
           totals = self._calculator.calculate_totals(formulation)
           per_ingredient = self._calculator.calculate_per_ingredient(formulation)
           self._exporter.export(formulation, totals, per_ingredient, output_path)
   ```

2. **Dependency Injection Container**
   ```python
   # config/container.py
   class Container:
       def __init__(self):
           self._api_key = os.getenv("USDA_API_KEY")
           self._cache = InMemoryCache()

       @property
       def food_repository(self) -> FoodRepository:
           return USDAFoodRepository(self._api_key, self._cache)

       @property
       def nutrient_calculator(self) -> NutrientCalculator:
           return NutrientCalculator()

       # ... otros servicios ...
   ```

#### Resultado
✅ Flujos de negocio explícitos
✅ Inyección de dependencias

---

### **FASE 7: Mejoras de Calidad (Prioridad: Baja)**

#### Objetivo
Pulir código y agregar tooling.

#### Tareas

1. **Type Hints Completos**
   - Pasar `mypy --strict` en todo el código
   - Agregar `py.typed` para soporte de librerías

2. **Linting y Formateo Automático**
   ```toml
   # pyproject.toml
   [tool.ruff]
   line-length = 100
   select = ["E", "F", "I", "N", "UP", "ANN", "S", "B", "A", "C4", "PL"]

   [tool.black]
   line-length = 100
   ```

3. **Pre-commit Hooks**
   ```yaml
   # .pre-commit-config.yaml
   repos:
     - repo: https://github.com/astral-sh/ruff-pre-commit
       rev: v0.1.0
       hooks:
         - id: ruff
     - repo: https://github.com/psf/black
       rev: 23.0.0
       hooks:
         - id: black
   ```

4. **Documentación**
   - README.md completo
   - Docstrings en todas las funciones públicas
   - Architecture Decision Records (ADRs)

5. **Estandarización de Idioma**
   - Elegir inglés para todo el código
   - Español solo para mensajes de usuario

#### Resultado
✅ Código profesional y consistente
✅ Documentación completa

---

## 📊 Métricas de Éxito

### Antes de Refactorización
- **Líneas en `main_window.py`**: 4554
- **Tests**: 0
- **Cobertura**: 0%
- **Complejidad ciclomática**: ~300+
- **Acoplamiento**: Alto (>10 dependencias por clase)

### Después de Refactorización
- **Líneas en `main_window.py`**: <500
- **Tests**: 100+ tests unitarios
- **Cobertura**: >80%
- **Complejidad ciclomática**: <10 por función
- **Acoplamiento**: Bajo (<5 dependencias por clase)
- **Type coverage**: 100%

---

## 🚀 Orden de Ejecución Recomendado

1. **FASE 1** (1-2 días): Setup de testing
2. **FASE 2** (2-3 días): Modelos del dominio
3. **FASE 3** (5-7 días): Servicios del dominio (crítico)
4. **FASE 4** (3-4 días): Infraestructura
5. **FASE 5** (7-10 días): UI refactoring (más complejo)
6. **FASE 6** (2-3 días): Use cases
7. **FASE 7** (2-3 días): Calidad

**Total estimado**: 22-32 días de desarrollo activo

---

## ⚠️ Riesgos y Mitigaciones

### Riesgo 1: Romper funcionalidad existente
**Mitigación**: Tests de caracterización antes de cada cambio

### Riesgo 2: Scope creep (agregar features durante refactoring)
**Mitigación**: Strict adherence a "refactor only, no new features"

### Riesgo 3: Rendimiento degradado
**Mitigación**: Benchmarks antes/después, especialmente en cálculos

### Riesgo 4: Overhead de abstracciones
**Mitigación**: Medir complejidad, evitar over-engineering

---

## 📚 Referencias

- **Clean Architecture**: Robert C. Martin
- **Refactoring**: Martin Fowler
- **SOLID Principles**: Uncle Bob
- **Qt Best Practices**: Qt Documentation
- **Python Type Hints**: PEP 484, 526, 544

---

## 🎯 Conclusión

Este proyecto tiene una **funcionalidad sólida** pero sufre de **deuda técnica acumulada** por concentrar toda la lógica en un solo archivo gigante. La estrategia propuesta aplica **principios de Clean Code** y **Clean Architecture** para:

1. **Separar responsabilidades** (UI, negocio, infraestructura)
2. **Hacer el código testable**
3. **Reducir acoplamiento**
4. **Facilitar mantenimiento futuro**
5. **Mejorar legibilidad y profesionalismo**

La refactorización es **incremental y segura**, comenzando por tests y modelos, luego servicios, y finalmente UI. Cada fase entrega valor y mantiene el sistema funcional.

**Recomendación**: Comenzar con **FASE 1 y 2** inmediatamente para establecer bases sólidas.
