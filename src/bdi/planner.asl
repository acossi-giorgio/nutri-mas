/* Agent lifecycle */
start.
weekday_order(monday, 0).
weekday_order(tuesday, 1).
weekday_order(wednesday, 2).
weekday_order(thursday, 3).
weekday_order(friday, 4).
weekday_order(saturday, 5).
weekday_order(sunday, 6).
meal_slot_order(breakfast, 0).
meal_slot_order(morning_snack, 1).
meal_slot_order(lunch, 2).
meal_slot_order(afternoon_snack, 3).
meal_slot_order(dinner, 4).
slot_weight(breakfast, 0.24).
slot_weight(morning_snack, 0.10).
slot_weight(lunch, 0.29).
slot_weight(afternoon_snack, 0.10).
slot_weight(dinner, 0.27).
/* Start the agent. */
+!start : true <-
    .log("Planner Agent ready").

/* Planning-state cleanup */
/* Active plan cleanup is delayed until every draft recipe is ready. */
/* Handle the clear active plan goal. */
+!clear_active_plan(Username) : planned_recipe_row(Username, D, S, N, T, I, Ins, C, P, Ca, F) <-
    -planned_recipe_row(Username, D, S, N, T, I, Ins, C, P, Ca, F);
    !clear_active_plan(Username).

/* Handle the clear active plan goal. */
+!clear_active_plan(Username) : planned_template_row(Username, D, S, T, C, P, Ca, F, Cat) <-
    -planned_template_row(Username, D, S, T, C, P, Ca, F, Cat);
    !clear_active_plan(Username).

/* Handle the clear active plan goal. */
+!clear_active_plan(Username) : slot_macro_target(Username, D, S, C, P, Ca, F) <-
    -slot_macro_target(Username, D, S, C, P, Ca, F);
    !clear_active_plan(Username).

/* Handle the clear active plan goal. */
+!clear_active_plan(_) : true <- true.

/* Handle the clear planning context goal. */
+!clear_planning_context(Username) : planning_context(Username, A, B, C, D) <-
    -planning_context(Username, A, B, C, D);
    !clear_planning_context(Username).

/* Handle the clear planning context goal. */
+!clear_planning_context(_) : true <- true.

/* Handle the clear planning phase goal. */
+!clear_planning_phase(Username) : planning_phase(Username, Phase) <-
    -planning_phase(Username, Phase);
    !clear_planning_phase(Username).

/* Handle the clear planning phase goal. */
+!clear_planning_phase(_) : true <- true.

/* Handle the clear domain candidates goal. */
+!clear_domain_candidates(Username) : template_domain_candidate(Username, S, N, C, P, Ca, F, Cat) <-
    -template_domain_candidate(Username, S, N, C, P, Ca, F, Cat);
    !clear_domain_candidates(Username).

/* Handle the clear domain candidates goal. */
+!clear_domain_candidates(_) : true <- true.

/* Handle the clear domain completions goal. */
+!clear_domain_completions(Username) : template_domain_complete(Username, Slot) <-
    -template_domain_complete(Username, Slot);
    !clear_domain_completions(Username).

/* Handle the clear domain completions goal. */
+!clear_domain_completions(_) : true <- true.

/* Handle the clear template assignments goal. */
+!clear_template_assignments(Username) : template_assignment(Username, I, D, S, N, C, P, Ca, F, Cat) <-
    -template_assignment(Username, I, D, S, N, C, P, Ca, F, Cat);
    !clear_template_assignments(Username).

/* Handle the clear template assignments goal. */
+!clear_template_assignments(_) : true <- true.

/* Handle the clear tried templates goal. */
+!clear_tried_templates(Username) : tried_template(Username, I, N) <-
    -tried_template(Username, I, N);
    !clear_tried_templates(Username).

/* Handle the clear tried templates goal. */
+!clear_tried_templates(_) : true <- true.

/* Handle the clear tried at goal. */
+!clear_tried_at(Username, Index) : tried_template(Username, Index, Name) <-
    -tried_template(Username, Index, Name);
    !clear_tried_at(Username, Index).

/* Handle the clear tried at goal. */
+!clear_tried_at(_, _) : true <- true.

/* Handle the clear draft recipes goal. */
+!clear_draft_recipes(Username) : draft_recipe_row(Username, D, S, N, T, I, Ins, C, P, Ca, F) <-
    -draft_recipe_row(Username, D, S, N, T, I, Ins, C, P, Ca, F);
    !clear_draft_recipes(Username).

/* Handle the clear draft recipes goal. */
+!clear_draft_recipes(_) : true <- true.

/* Handle the clear draft macro targets goal. */
+!clear_draft_macro_targets(Username) : draft_slot_macro_target(Username, D, S, C, P, Ca, F) <-
    -draft_slot_macro_target(Username, D, S, C, P, Ca, F);
    !clear_draft_macro_targets(Username).

/* Handle the clear draft macro targets goal. */
+!clear_draft_macro_targets(_) : true <- true.

/* Handle the clear pending recipe slot goal. */
+!clear_pending_recipe_slot(Username) : pending_recipe_slot(Username, I, D, S, T, C, P, Ca, F, Cat) <-
    -pending_recipe_slot(Username, I, D, S, T, C, P, Ca, F, Cat);
    !clear_pending_recipe_slot(Username).

/* Handle the clear pending recipe slot goal. */
+!clear_pending_recipe_slot(_) : true <- true.

/* Handle the clear search steps goal. */
+!clear_search_steps(Username) : search_step(Username, Index) <-
    -search_step(Username, Index);
    !clear_search_steps(Username).

/* Handle the clear search steps goal. */
+!clear_search_steps(_) : true <- true.

/* Handle the clear used dish goal. */
+!clear_used_dish : used_dish(Day, Dish) <-
    -used_dish(Day, Dish);
    !clear_used_dish.

/* Handle the clear used dish goal. */
+!clear_used_dish : true <- true.

/* Handle the clear category count goal. */
+!clear_category_count : category_count(Category, Count) <-
    -category_count(Category, Count);
    !clear_category_count.

/* Handle the clear category count goal. */
+!clear_category_count : true <- true.

/* Handle the clear planning draft goal. */
+!clear_planning_draft(Username) : true <-
    !clear_planning_phase(Username);
    !clear_domain_candidates(Username);
    !clear_domain_completions(Username);
    !clear_template_assignments(Username);
    !clear_tried_templates(Username);
    !clear_draft_recipes(Username);
    !clear_draft_macro_targets(Username);
    !clear_pending_recipe_slot(Username);
    !clear_search_steps(Username);
    !clear_used_dish;
    !clear_category_count.

/* Weekly-plan initialization */
/* Handle the slot macro target values goal. */
+!slot_macro_target_values(Username, Slot, DailyCalories, TargetProtein, TargetCarbs, TargetFat) :
        planning_context(Username, _, DailyCalories, Weight, Activity) &
        slot_weight(Slot, SlotWeight) <-
    .calculate_slot_macro_targets(DailyCalories, Weight, Activity, SlotWeight,
        TargetProtein, TargetCarbs, TargetFat).

/* Handle the build week plan goal. */
+!build_week_plan(Username, DietType) : true <-
    .log("Planner - triggering BDI autonomous planning system");
    +ready_to_plan(Username, DietType, 2000, 70.0, "moderate", "").

/* Handle the build week plan goal. */
+!build_week_plan(Username, DietType, DailyCalories, Weight, Activity, Allergens) : true <-
    .log("Planner - triggering BDI autonomous planning system");
    +ready_to_plan(Username, DietType, DailyCalories, Weight, Activity, Allergens).

/* Handle the build week plan event. */
+build_week_plan(Username)[source(_)] : true <-
    -build_week_plan(Username);
    !build_week_plan(Username, "omnivore").

/* Handle the build week plan event. */
+build_week_plan(Username, DietType)[source(_)] : true <-
    -build_week_plan(Username, DietType);
    !build_week_plan(Username, DietType).

/* Handle the build week plan event. */
+build_week_plan(Username, DietType, DailyCalories, Weight, Activity, Allergens)[source(_)] : true <-
    -build_week_plan(Username, DietType, DailyCalories, Weight, Activity, Allergens);
    !build_week_plan(Username, DietType, DailyCalories, Weight, Activity, Allergens).

/* Handle the ready to plan event. */
+ready_to_plan(Username, DietType, Target, Weight, Activity, Allergens) : planning_in_progress(Username) <-
    -ready_to_plan(Username, DietType, Target, Weight, Activity, Allergens);
    .send("gateway@localhost", tell, planning_failed(Username, "planning_in_progress")).

/* Handle the ready to plan event. */
+ready_to_plan(Username, DietType, Target, Weight, Activity, Allergens) : true <-
    -ready_to_plan(Username, DietType, Target, Weight, Activity, Allergens);
    .log("Planner - collecting template domains before AgentSpeak backtracking");
    +planning_in_progress(Username);
    !clear_planning_draft(Username);
    !clear_planning_context(Username);
    !reset_category_counts;
    +planning_context(Username, DietType, Target, Weight, Activity);
    +planning_phase(Username, template_domains);
    !request_template_domains(Username, DietType, Target).

/* Handle the reset category counts goal. */
+!reset_category_counts : true <-
    +category_count(red_meat, 0);
    +category_count(vegetable, 0);
    +category_count(poultry, 0);
    +category_count(fish, 0);
    +category_count(egg, 0);
    +category_count(dairy, 0);
    +category_count(legume, 0);
    +category_count(grain, 0);
    +category_count(fruit, 0);
    +category_count(nuts, 0);
    +category_count(breakfast, 0);
    +category_count(morning_snack, 0);
    +category_count(lunch, 0);
    +category_count(afternoon_snack, 0);
    +category_count(dinner, 0).

/* Template-domain collection */
/* Handle the request template domains goal. */
+!request_template_domains(Username, DietType, Target) : true <-
    !request_template_domain(Username, breakfast, DietType, Target);
    !request_template_domain(Username, morning_snack, DietType, Target);
    !request_template_domain(Username, lunch, DietType, Target);
    !request_template_domain(Username, afternoon_snack, DietType, Target);
    !request_template_domain(Username, dinner, DietType, Target).

/* Handle the request template domain goal. */
+!request_template_domain(Username, Slot, DietType, Target) : true <-
    !slot_macro_target_values(Username, Slot, Target, TargetProtein, TargetCarbs, TargetFat);
    .send("chef@localhost", achieve,
        template_domain_request(Username, Slot, DietType, Target,
            TargetProtein, TargetCarbs, TargetFat)).

/* Handle the template domain candidate event. */
+template_domain_candidate(Username, Slot, Name, Calories, Protein, Carbs, Fat, Category)[source(_)] :
        planning_phase(Username, template_domains) <- true.

/* Handle the template domain candidate event. */
+template_domain_candidate(Username, Slot, Name, Calories, Protein, Carbs, Fat, Category)[source(_)] : true <-
    -template_domain_candidate(Username, Slot, Name, Calories, Protein, Carbs, Fat, Category).

/* Handle the template domain complete event. */
+template_domain_complete(Username, Slot)[source(_)] : planning_phase(Username, template_domains) <-
    !maybe_start_template_search(Username).

/* Handle the template domain complete event. */
+template_domain_complete(Username, Slot)[source(_)] : true <-
    -template_domain_complete(Username, Slot).

/* Handle the maybe start template search goal. */
+!maybe_start_template_search(Username) :
        planning_phase(Username, template_domains) &
        template_domain_complete(Username, breakfast) &
        template_domain_complete(Username, morning_snack) &
        template_domain_complete(Username, lunch) &
        template_domain_complete(Username, afternoon_snack) &
        template_domain_complete(Username, dinner) <-
    -planning_phase(Username, template_domains);
    +planning_phase(Username, template_search);
    .log("Planner - all domains ready, starting complete AgentSpeak backtracking");
    +search_step(Username, 0).

/* Handle the maybe start template search goal. */
+!maybe_start_template_search(_) : true <- true.

/* Search events are intentionally flat: no asynchronous intention stack is retained. */
/* Complete backtracking search over weekly slots */
/* Handle the search step event. */
+search_step(Username, Index) :
        planning_phase(Username, template_search) &
        plan_position(Index, Day, Slot) &
        template_domain_candidate(Username, Slot, Name, Calories, Protein, Carbs, Fat, Category) &
        not tried_template(Username, Index, Name) &
        used_dish(Day, Name) <-
    -search_step(Username, Index);
    +tried_template(Username, Index, Name);
    +search_step(Username, Index).

/* Handle the search step event. */
+search_step(Username, Index) :
        planning_phase(Username, template_search) &
        planning_context(Username, DietType, _, _, _) &
        plan_position(Index, Day, Slot) &
        template_domain_candidate(Username, Slot, Name, Calories, Protein, Carbs, Fat, Category) &
        not tried_template(Username, Index, Name) &
        nutrition_rule_slot(DietType, Category, Slot, _, MaxPerWeek) &
        category_count(Category, Count) &
        Count >= MaxPerWeek <-
    -search_step(Username, Index);
    +tried_template(Username, Index, Name);
    +search_step(Username, Index).

/* Handle the search step event. */
+search_step(Username, Index) :
        planning_phase(Username, template_search) &
        planning_context(Username, DietType, _, _, _) &
        plan_position(Index, Day, Slot) &
        template_domain_candidate(Username, Slot, Name, Calories, Protein, Carbs, Fat, Category) &
        not tried_template(Username, Index, Name) &
        not used_dish(Day, Name) &
        .minimums_unreachable_after(Username, Index, Day, Slot, Name, Category, DietType) <-
    -search_step(Username, Index);
    +tried_template(Username, Index, Name);
    +search_step(Username, Index).

/* Handle the search step event. */
+search_step(Username, Index) :
        planning_phase(Username, template_search) &
        planning_context(Username, DietType, _, _, _) &
        plan_position(Index, Day, Slot) &
        template_domain_candidate(Username, Slot, Name, Calories, Protein, Carbs, Fat, Category) &
        not tried_template(Username, Index, Name) &
        not used_dish(Day, Name) &
        nutrition_rule_slot(DietType, Category, Slot, MinPerWeek, _) &
        category_count(Category, Count) &
        Count < MinPerWeek &
        .minimums_reachable_after(Username, Index, Day, Slot, Name, Category, DietType) <-
    -search_step(Username, Index);
    !accept_template(Username, Index, Day, Slot, Name, Calories, Protein, Carbs, Fat, Category, DietType).

/* Handle the search step event. */
+search_step(Username, Index) :
        planning_phase(Username, template_search) &
        planning_context(Username, DietType, _, _, _) &
        plan_position(Index, Day, Slot) &
        template_domain_candidate(Username, Slot, Name, Calories, Protein, Carbs, Fat, Category) &
        not tried_template(Username, Index, Name) &
        not used_dish(Day, Name) &
        .minimums_reachable_after(Username, Index, Day, Slot, Name, Category, DietType) <-
    -search_step(Username, Index);
    !accept_template(Username, Index, Day, Slot, Name, Calories, Protein, Carbs, Fat, Category, DietType).

/* Handle the accept template goal. */
+!accept_template(Username, Index, Day, Slot, Name, Calories, Protein, Carbs, Fat, Category, DietType) : true <-
    +tried_template(Username, Index, Name);
    +template_assignment(Username, Index, Day, Slot, Name, Calories, Protein, Carbs, Fat, Category);
    +draft_slot_macro_target(Username, Day, Slot, Calories, Protein, Carbs, Fat);
    +used_dish(Day, Name);
    !increment_rule_category_count(DietType, Slot, Category);
    !increment_category_count(Slot);
    Next = Index + 1;
    !clear_tried_at(Username, Next);
    +search_step(Username, Next).

/* Handle the search step event. */
+search_step(Username, 35) :
        planning_phase(Username, template_search) &
        planning_context(Username, DietType, _, _, _) &
        nutrition_rule(DietType, Category, _, MinPerWeek, _) &
        category_count(Category, Count) &
        Count < MinPerWeek <-
    -search_step(Username, 35);
    .log("Planner - complete assignment violates a minimum, backtracking");
    !backtrack_from(Username, 35).

/* Handle the search step event. */
+search_step(Username, 35) :
        planning_phase(Username, template_search) &
        planning_context(Username, DietType, _, _, _) &
        nutrition_rule(DietType, Category, _, _, MaxPerWeek) &
        category_count(Category, Count) &
        Count > MaxPerWeek <-
    -search_step(Username, 35);
    !backtrack_from(Username, 35).

/* Handle the search step event. */
+search_step(Username, 35) : planning_phase(Username, template_search) <-
    -search_step(Username, 35);
    -planning_phase(Username, template_search);
    +planning_phase(Username, recipe_generation);
    .log("Planner - complete template plan found; starting Cook materialization");
    !request_draft_recipe(Username, 0).

/* Handle the search step event. */
+search_step(Username, Index) :
        planning_phase(Username, template_search) & Index > 0 <-
    -search_step(Username, Index);
    !backtrack_from(Username, Index).

/* Handle the search step event. */
+search_step(Username, 0) : planning_phase(Username, template_search) <-
    -search_step(Username, 0);
    !abort_weekly_planning(Username, "no_template_solution").

/* Handle the backtrack from goal. */
+!backtrack_from(Username, Index) : Index > 0 <-
    Previous = Index - 1;
    !rollback_assignment(Username, Previous);
    +search_step(Username, Previous).

/* Handle the rollback assignment goal. */
+!rollback_assignment(Username, Index) :
        planning_context(Username, DietType, _, _, _) &
        template_assignment(Username, Index, Day, Slot, Name, Calories, Protein, Carbs, Fat, Category) <-
    -template_assignment(Username, Index, Day, Slot, Name, Calories, Protein, Carbs, Fat, Category);
    -draft_slot_macro_target(Username, Day, Slot, Calories, Protein, Carbs, Fat);
    -used_dish(Day, Name);
    !decrement_rule_category_count(DietType, Slot, Category);
    !decrement_category_count(Slot).

/* Search counters and nutrition-rule bookkeeping */
/* Handle the increment category count goal. */
+!increment_category_count(Category) : category_count(Category, Count) <-
    -category_count(Category, Count);
    NewCount = Count + 1;
    +category_count(Category, NewCount).

/* Handle the increment category count goal. */
+!increment_category_count(Category) : true <-
    +category_count(Category, 1).

/* Handle the decrement category count goal. */
+!decrement_category_count(Category) : category_count(Category, Count) & Count > 0 <-
    -category_count(Category, Count);
    NewCount = Count - 1;
    +category_count(Category, NewCount).

/* Handle the decrement category count goal. */
+!decrement_category_count(_) : true <- true.

/* Handle the increment rule category count goal. */
+!increment_rule_category_count(DietType, Slot, Category) :
        nutrition_rule_slot(DietType, Category, Slot, _, _) <-
    !increment_category_count(Category).

/* Handle the increment rule category count goal. */
+!increment_rule_category_count(_, _, _) : true <- true.

/* Handle the decrement rule category count goal. */
+!decrement_rule_category_count(DietType, Slot, Category) :
        nutrition_rule_slot(DietType, Category, Slot, _, _) <-
    !decrement_category_count(Category).

/* Handle the decrement rule category count goal. */
+!decrement_rule_category_count(_, _, _) : true <- true.

/* Recipe generation and runtime rebalancing */
/* Handle the request draft recipe goal. */
+!request_draft_recipe(Username, Index) :
        template_assignment(Username, Index, Day, Slot, Template, Calories, Protein, Carbs, Fat, Category) <-
    +pending_recipe_slot(Username, Index, Day, Slot, Template, Calories, Protein, Carbs, Fat, Category);
    .request_recipe(Username, Day, Slot, Template, Calories, Protein, Carbs, Fat).

/* Runtime rebalancing scales the persisted slot macros, so it also works after restart. */
/* Handle the runtime rebalance macro targets goal. */
+!runtime_rebalance_macro_targets(Username, Day, Slot, TargetCalories, TargetProtein, TargetCarbs, TargetFat) :
        planned_template_row(Username, Day, Slot, _, BaseCalories, BaseProtein, BaseCarbs, BaseFat, _) &
        BaseCalories > 0 <-
    .scale_runtime_macro_targets(TargetCalories, BaseCalories, BaseProtein, BaseCarbs, BaseFat,
        TargetProtein, TargetCarbs, TargetFat).

/* Handle the runtime rebalance macro targets goal. */
+!runtime_rebalance_macro_targets(Username, Day, Slot, TargetCalories, TargetProtein, TargetCarbs, TargetFat) :
        planned_recipe_row(Username, Day, Slot, _, _, _, _, BaseCalories, BaseProtein, BaseCarbs, BaseFat) &
        BaseCalories > 0 <-
    .scale_runtime_macro_targets(TargetCalories, BaseCalories, BaseProtein, BaseCarbs, BaseFat,
        TargetProtein, TargetCarbs, TargetFat).

/* Handle the runtime rebalance macro targets goal. */
+!runtime_rebalance_macro_targets(_, _, _, TargetCalories, TargetProtein, TargetCarbs, TargetFat) : true <-
    TargetProtein = TargetCalories * 0.20 / 4;
    TargetCarbs = TargetCalories * 0.50 / 4;
    TargetFat = TargetCalories * 0.30 / 9.

/* Handle the rebalance slot goal. */
+!rebalance_slot(Username, Date, Day, Slot, DietType, TargetCalories, Excluded)[source(_)] : true <-
    slot_weight(Slot, SlotWeight);
    ChefDailyTarget = TargetCalories / SlotWeight;
    !runtime_rebalance_macro_targets(Username, Day, Slot, TargetCalories,
        TargetProtein, TargetCarbs, TargetFat);
    +pending_rebalance_slot(Username, Date, Day, Slot, TargetCalories, TargetProtein, TargetCarbs, TargetFat, Excluded);
    .send("chef@localhost", achieve,
        plan_template_request(Username, Slot, DietType, ChefDailyTarget, strict, Excluded,
            TargetProtein, TargetCarbs, TargetFat)).

/* Handle the rebalance slot goal. */
+!rebalance_slot(Username, Date, _, Slot, _, _, _)[source(_)] : true <-
    .log("Planner - runtime rebalance request failed before template selection");
    .send("nutritionist@localhost", tell, rebalance_template_failed(Username, Date, Slot)).

/* Handle the plan template response event. */
+plan_template_response(Username, Slot, Dish, Calories, Protein, Carbs, Fat, Category)[source(_)] :
        pending_rebalance_slot(Username, Date, Day, Slot, TargetCalories, TargetProtein, TargetCarbs, TargetFat, Excluded) <-
    -plan_template_response(Username, Slot, Dish, Calories, Protein, Carbs, Fat, Category);
    -pending_rebalance_slot(Username, Date, Day, Slot, TargetCalories, TargetProtein, TargetCarbs, TargetFat, Excluded);
    !prepare_runtime_recipe(Username, Date, Day, Slot, Dish, TargetCalories,
        TargetProtein, TargetCarbs, TargetFat, "rebalance").

/* Handle the plan template failed event. */
+plan_template_failed(Username, Slot)[source(_)] :
        pending_rebalance_slot(Username, Date, Day, Slot, TargetCalories, TargetProtein, TargetCarbs, TargetFat, Excluded) <-
    -plan_template_failed(Username, Slot);
    -pending_rebalance_slot(Username, Date, Day, Slot, TargetCalories, TargetProtein, TargetCarbs, TargetFat, Excluded);
    .send("nutritionist@localhost", tell, rebalance_template_failed(Username, Date, Slot)).

/* Handle the clear pending runtime slot goal. */
+!clear_pending_runtime_slot(Username, Date, Slot) :
        pending_runtime_recipe_slot(Username, Date, Day, Slot, Template, Calories, Protein, Carbs, Fat, Purpose) <-
    -pending_runtime_recipe_slot(Username, Date, Day, Slot, Template, Calories, Protein, Carbs, Fat, Purpose);
    !clear_pending_runtime_slot(Username, Date, Slot).

/* Handle the clear pending runtime slot goal. */
+!clear_pending_runtime_slot(_, _, _) : true <- true.

/* Handle the prepare runtime recipe goal. */
+!prepare_runtime_recipe(Username, Date, Day, Slot, Template, Calories, Protein, Carbs, Fat, Purpose) : true <-
    !clear_pending_runtime_slot(Username, Date, Slot);
    +pending_runtime_recipe_slot(Username, Date, Day, Slot, Template, Calories, Protein, Carbs, Fat, Purpose);
    .request_recipe(Username, Day, Slot, Template, Calories, Protein, Carbs, Fat).

/* Handle the recipe event. */
+recipe(Username, RecipeDay, RecipeSlot, Template, Name, Ingredients, Instructions, Calories, Protein, Carbs, Fat)[source(_)] :
        pending_runtime_recipe_slot(Username, Date, PendingDay, PendingSlot, Template, TargetCalories, TargetProtein, TargetCarbs, TargetFat, "rebalance") &
        .same_text(RecipeDay, PendingDay) & .same_text(RecipeSlot, PendingSlot) <-
    -recipe(Username, RecipeDay, RecipeSlot, Template, Name, Ingredients, Instructions, Calories, Protein, Carbs, Fat);
    -pending_runtime_recipe_slot(Username, Date, PendingDay, PendingSlot, Template, TargetCalories, TargetProtein, TargetCarbs, TargetFat, "rebalance");
    .send("nutritionist@localhost", tell,
        rebalance_recipe_response(Username, Date, PendingSlot, Template, Name, Calories, Protein, Carbs, Fat)).

/* Handle the recipe event. */
+recipe(Username, Day, Slot, Template, Name, Ingredients, Instructions, Calories, Protein, Carbs, Fat)[source(_)] :
        pending_recipe_slot(Username, Index, Day, Slot, Template, TargetCalories, TargetProtein, TargetCarbs, TargetFat, Category) &
        Index < 34 <-
    -recipe(Username, Day, Slot, Template, Name, Ingredients, Instructions, Calories, Protein, Carbs, Fat);
    -pending_recipe_slot(Username, Index, Day, Slot, Template, TargetCalories, TargetProtein, TargetCarbs, TargetFat, Category);
    +draft_recipe_row(Username, Day, Slot, Name, Template, Ingredients, Instructions, Calories, Protein, Carbs, Fat);
    Next = Index + 1;
    !request_draft_recipe(Username, Next).

/* Handle the recipe event. */
+recipe(Username, Day, Slot, Template, Name, Ingredients, Instructions, Calories, Protein, Carbs, Fat)[source(_)] :
        pending_recipe_slot(Username, 34, Day, Slot, Template, TargetCalories, TargetProtein, TargetCarbs, TargetFat, Category) <-
    -recipe(Username, Day, Slot, Template, Name, Ingredients, Instructions, Calories, Protein, Carbs, Fat);
    -pending_recipe_slot(Username, 34, Day, Slot, Template, TargetCalories, TargetProtein, TargetCarbs, TargetFat, Category);
    +draft_recipe_row(Username, Day, Slot, Name, Template, Ingredients, Instructions, Calories, Protein, Carbs, Fat);
    -planning_phase(Username, recipe_generation);
    +planning_phase(Username, awaiting_commit);
    .log("Planner - all draft recipes ready, requesting atomic plan replacement");
    .send("nutritionist@localhost", achieve, clear_planned_recipes(Username)).

/* Handle the recipe event. */
+recipe(Username, Day, Slot, Template, Name, Ingredients, Instructions, Calories, Protein, Carbs, Fat)[source(_)] : true <-
    -recipe(Username, Day, Slot, Template, Name, Ingredients, Instructions, Calories, Protein, Carbs, Fat);
    .log("Planner - ignoring late or duplicate prepared recipe").

/* Draft commit and failure handling */
/* Handle the plan storage cleared event. */
+plan_storage_cleared(Username)[source(_)] : planning_phase(Username, awaiting_commit) <-
    -plan_storage_cleared(Username);
    !clear_active_plan(Username);
    !promote_draft_plan(Username).

/* Handle the plan storage cleared event. */
+plan_storage_cleared(Username)[source(_)] : true <-
    -plan_storage_cleared(Username).

/* Handle the promote draft plan goal. */
+!promote_draft_plan(Username) :
        template_assignment(Username, Index, Day, Slot, Template, TargetCalories, TargetProtein, TargetCarbs, TargetFat, Category) &
        draft_recipe_row(Username, Day, Slot, Name, Template, Ingredients, Instructions, Calories, Protein, Carbs, Fat) <-
    -template_assignment(Username, Index, Day, Slot, Template, TargetCalories, TargetProtein, TargetCarbs, TargetFat, Category);
    -draft_recipe_row(Username, Day, Slot, Name, Template, Ingredients, Instructions, Calories, Protein, Carbs, Fat);
    -draft_slot_macro_target(Username, Day, Slot, TargetCalories, TargetProtein, TargetCarbs, TargetFat);
    +planned_template_row(Username, Day, Slot, Template, TargetCalories, TargetProtein, TargetCarbs, TargetFat, Category);
    +planned_recipe_row(Username, Day, Slot, Name, Template, Ingredients, Instructions, Calories, Protein, Carbs, Fat);
    +slot_macro_target(Username, Day, Slot, TargetCalories, TargetProtein, TargetCarbs, TargetFat);
    .send("nutritionist@localhost", tell,
        planned_recipe_row(Username, Day, Slot, Name, Template, Ingredients, Instructions, Calories, Protein, Carbs, Fat));
    .send("nutritionist@localhost", tell,
        slot_macro_target(Username, Day, Slot, TargetCalories, TargetProtein, TargetCarbs, TargetFat));
    !promote_draft_plan(Username).

/* Handle the promote draft plan goal. */
+!promote_draft_plan(Username) : planning_phase(Username, awaiting_commit) <-
    -planning_phase(Username, awaiting_commit);
    -planning_in_progress(Username);
    !clear_planning_draft(Username);
    .log("Planner - backtracked template plan committed successfully");
    .send_plan(Username, "weekly_plan").

/* Handle the recipe failed event. */
+recipe_failed(Username, Day, Slot, Reason)[source(_)] : true <-
    -recipe_failed(Username, Day, Slot, Reason);
    !handle_recipe_failure(Username, Day, Slot).

/* Handle the handle recipe failure goal. */
+!handle_recipe_failure(Username, Day, Slot) :
        pending_recipe_slot(Username, Index, Day, Slot, Template, Calories, Protein, Carbs, Fat, Category) <-
    -pending_recipe_slot(Username, Index, Day, Slot, Template, Calories, Protein, Carbs, Fat, Category);
    !abort_weekly_planning(Username, "cook_error").

/* Handle the handle recipe failure goal. */
+!handle_recipe_failure(Username, Day, Slot) :
        pending_runtime_recipe_slot(Username, Date, Day, Slot, Template, Calories, Protein, Carbs, Fat, "rebalance") <-
    -pending_runtime_recipe_slot(Username, Date, Day, Slot, Template, Calories, Protein, Carbs, Fat, "rebalance");
    .send("nutritionist@localhost", tell, rebalance_recipe_failed(Username, Date, Slot)).

/* Handle the handle recipe failure goal. */
+!handle_recipe_failure(_, _, _) : true <- true.

/* Handle the abort weekly planning goal. */
+!abort_weekly_planning(Username, Reason) : true <-
    -planning_in_progress(Username);
    !clear_planning_draft(Username);
    .concat("Planner - weekly planning aborted (", Reason, LogPrefix);
    .concat(LogPrefix, "); active plan preserved", LogMsg);
    .log(LogMsg);
    .send("gateway@localhost", tell, planning_failed(Username, Reason)).

/* Plan queries */
/* Handle the get plan goal. */
+!get_plan(Username)[source(_)] : true <-
    .send_plan(Username, "current_plan").

/* Handle the get plan day context event. */
+get_plan_day_context(Username, Day)[source(_)] : true <-
    -get_plan_day_context(Username, Day);
    .send_plan_day_context(Username, Day).
