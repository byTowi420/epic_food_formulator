# Runtime audit report

Trace file: C:\Users\jtorres\OneDrive - Universidad Católica del Uruguay\VS CODE\Programacion II\food_formulator\tmp_blobs\runtime_trace.json
Total defs: 423
Executed defs: 285
Not executed: 138

Notes:
- Results depend on which UI flows you exercised.
- Some callbacks may only run under specific conditions.
- Matching uses file+line to account for mixin methods.

## Not executed (candidates)

### application/use_cases.py
- L23: SearchFoodsUseCase.__init__
- L26: SearchFoodsUseCase.execute
- L59: AddIngredientUseCase.__init__
- L67: AddIngredientUseCase.execute
- L140: SaveFormulationUseCase.__init__
- L143: SaveFormulationUseCase.execute
- L159: LoadFormulationUseCase.__init__
- L162: LoadFormulationUseCase.execute
- L211: AdjustFormulationUseCase.__init__
- L214: AdjustFormulationUseCase.execute

### config/container.py
- L69: Container.food_repository
- L79: Container.json_repository
- L117: Container.label_generator
- L125: Container.search_foods
- L132: Container.add_ingredient
- L149: Container.save_formulation
- L156: Container.load_formulation
- L173: Container.adjust_formulation

### domain/exceptions.py
- L53: USDAHTTPError.__init__
- L90: FormulationImportError.__init__

### domain/models.py
- L34: Nutrient.scale
- L67: Food.get_nutrient
- L75: Food.has_nutrient
- L97: Ingredient.fdc_id
- L102: Ingredient.description
- L106: Ingredient.calculate_percentage
- L112: Ingredient.get_nutrient_amount
- L171: Formulation.get_locked_ingredients
- L175: Formulation.get_unlocked_ingredients
- L179: Formulation.get_total_locked_weight
- L186: Formulation.clear

### domain/services/formulation_service.py
- L16: FormulationService.adjust_to_target_weight
- L69: FormulationService.distribute_percentages
- L94: FormulationService.normalize_to_100g
- L134: FormulationService.lock_ingredient
- L148: FormulationService.unlock_ingredient
- L162: FormulationService.set_ingredient_amount

### domain/services/label_generator.py
- L15: LabelRow.__init__
- L47: LabelGenerator.generate_label
- L254: LabelGenerator._get_nutrient_flexible
- L278: LabelGenerator._format_amount
- L287: LabelGenerator._calc_dv_percent

### domain/services/nutrient_calculator.py
- L67: NutrientCalculator.calculate_per_ingredient
- L95: NutrientCalculator.calculate_energy
- L126: NutrientCalculator.get_nutrient_value

### domain/services/nutrient_ordering.py
- L135: NutrientOrdering.infer_unit

### infrastructure/api/cache.py
- L16: Cache.get
- L27: Cache.set
- L37: Cache.clear
- L41: Cache.delete
- L62: InMemoryCache.get
- L77: InMemoryCache.set
- L88: InMemoryCache.clear
- L93: InMemoryCache.delete
- L98: InMemoryCache.size
- L110: NullCache.get
- L114: NullCache.set
- L117: NullCache.clear
- L120: NullCache.delete

### infrastructure/api/usda_repository.py
- L31: _normalize_food_payload
- L87: FoodRepository.search
- L107: FoodRepository.get_by_id
- L127: FoodRepository.has_cached
- L148: USDAFoodRepository.__init__
- L168: USDAFoodRepository._create_session
- L193: USDAFoodRepository.search
- L263: USDAFoodRepository.get_by_id
- L324: USDAFoodRepository.has_cached
- L336: USDAFoodRepository._request

### infrastructure/persistence/json_repository.py
- L18: JSONFormulationRepository.__init__
- L27: JSONFormulationRepository.save
- L48: JSONFormulationRepository.load
- L77: JSONFormulationRepository.list_files
- L88: JSONFormulationRepository.delete
- L104: JSONFormulationRepository._formulation_to_dict
- L132: JSONFormulationRepository._dict_to_formulation

### ui/main_window.py
- L79: MainWindow.food_repository

### ui/presenters/formulation_presenter.py
- L66: FormulationPresenter.add_ingredient
- L144: FormulationPresenter.remove_ingredient
- L185: FormulationPresenter.toggle_lock
- L219: FormulationPresenter.get_label_rows
- L234: FormulationPresenter.adjust_to_target_weight
- L245: FormulationPresenter.normalize_to_100g
- L256: FormulationPresenter.clear
- L260: FormulationPresenter.load_from_file
- L269: FormulationPresenter.save_to_file
- L329: FormulationPresenter._export_to_excel_legacy
- L612: FormulationPresenter.hydrate_items
- L763: FormulationPresenter.split_header_unit
- L769: FormulationPresenter.nutrients_by_header
- L806: FormulationPresenter.collect_nutrient_columns

### ui/presenters/label_presenter.py
- L334: LabelPresenter.convert_label_amount_unit
- L343: LabelPresenter.format_fraction_amount

### ui/presenters/search_presenter.py
- L29: SearchPresenter.search
- L57: SearchPresenter.search_all
- L121: SearchPresenter.get_total_count
- L124: SearchPresenter.get_food_details
- L186: SearchPresenter.build_details_status
- L219: SearchPresenter.prefetch_food_details
- L233: SearchPresenter.get_last_results
- L241: SearchPresenter.get_last_query
- L257: SearchPresenter._sort_results
- L271: SearchPresenter._filter_results_by_query

### ui/tabs/formulation_tab.py
- L256: FormulationTabMixin.on_edit_quantity_clicked
- L611: FormulationTabMixin._on_import_error
- L660: FormulationTabMixin._format_mass_amount
- L723: FormulationTabMixin._hydrate_items
- L1288: FormulationTabMixin._on_add_error

### ui/tabs/label_tab.py
- L463: LabelTabMixin._format_fraction_amount
- L466: LabelTabMixin._fraction_from_ratio
- L556: LabelTabMixin._format_number_for_unit
- L559: LabelTabMixin._format_additional_amount
- L562: LabelTabMixin._format_nutrient_amount
- L565: LabelTabMixin._format_vd_value
- L568: LabelTabMixin._format_manual_amount
- L571: LabelTabMixin._format_manual_vd
- L864: LabelTabMixin._human_join
- L873: LabelTabMixin._parse_label_mapping
- L879: LabelTabMixin._find_total_entry
- L888: LabelTabMixin._convert_label_amount_unit
- L893: LabelTabMixin._factor_for_energy
- L897: LabelTabMixin._compute_energy_label_values
- L909: LabelTabMixin._label_amount_from_totals
- L922: LabelTabMixin._effective_label_nutrient
- L1232: LabelTabMixin._remove_image_background
- L1255: LabelTabMixin._strip_to_strokes
- L1293: LabelTabMixin._clear_white_background

### ui/tabs/search_tab.py
- L190: SearchTabMixin.on_prev_page_clicked
- L239: SearchTabMixin._fetch_all_pages
- L313: SearchTabMixin.on_fdc_search_clicked
- L348: SearchTabMixin.on_add_selected_clicked
- L356: SearchTabMixin.on_formulation_preview_double_clicked
- L416: SearchTabMixin._on_search_error
- L422: SearchTabMixin._on_details_success
- L432: SearchTabMixin._on_details_error

### ui/workers.py
- L23: ApiWorker.run
- L53: ImportWorker.run
- L125: AddWorker.run