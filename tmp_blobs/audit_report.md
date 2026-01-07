# Runtime audit report

Trace file: tmp_blobs\runtime_trace_merged.json
Total defs: 384
Executed defs: 250
Not executed: 134

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
- L67: Container.food_repository
- L77: Container.json_repository
- L116: Container.search_foods
- L123: Container.add_ingredient
- L140: Container.save_formulation
- L147: Container.load_formulation
- L164: Container.adjust_formulation

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
- L221: FormulationPresenter._export_to_excel_legacy
- L604: FormulationPresenter.split_header_unit
- L610: FormulationPresenter.nutrients_by_header
- L647: FormulationPresenter.collect_nutrient_columns

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
- L631: FormulationTabMixin._on_import_error
- L637: FormulationTabMixin._reset_import_ui_state
- L646: FormulationTabMixin._show_import_warnings
- L667: FormulationTabMixin._total_weight
- L671: FormulationTabMixin._is_percent_mode
- L674: FormulationTabMixin._current_mass_unit
- L677: FormulationTabMixin._quantity_mode_label
- L680: FormulationTabMixin._set_quantity_mode
- L693: FormulationTabMixin._mass_decimals
- L696: FormulationTabMixin._display_amount_for_unit
- L701: FormulationTabMixin._amount_to_percent
- L706: FormulationTabMixin._update_quantity_headers
- L723: FormulationTabMixin._set_item_enabled
- L735: FormulationTabMixin._apply_column_state
- L750: FormulationTabMixin._can_edit_column
- L758: FormulationTabMixin._populate_formulation_tables
- L812: FormulationTabMixin._populate_totals_table
- L851: FormulationTabMixin._calculate_totals
- L868: FormulationTabMixin._create_question_icon
- L886: FormulationTabMixin._refresh_formulation_views
- L899: FormulationTabMixin._select_preview_row
- L925: FormulationTabMixin._show_nutrients_for_row
- L933: FormulationTabMixin._show_nutrients_for_selected_preview
- L942: FormulationTabMixin._export_formulation_to_excel
- L954: FormulationTabMixin._add_row_to_formulation
- L988: FormulationTabMixin._start_add_fetch
- L1027: FormulationTabMixin._on_add_progress
- L1032: FormulationTabMixin._on_add_finished
- L1041: FormulationTabMixin._reset_add_ui_state
- L1048: FormulationTabMixin._format_amount_for_status
- L1058: FormulationTabMixin._prompt_quantity
- L1102: FormulationTabMixin._edit_quantity_for_row
- L1135: FormulationTabMixin._apply_percent_edit
- L1209: FormulationTabMixin._run_in_thread
- L1238: FormulationTabMixin._on_add_details_loaded
- L1282: FormulationTabMixin._on_add_error
- L1288: FormulationTabMixin._upgrade_item_to_full
- L1292: FormulationTabMixin.on_totals_checkbox_changed
- L1305: FormulationTabMixin.on_toggle_export_clicked

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
- L24: ApiWorker.run
- L54: ImportWorker.run
- L143: AddWorker.run