/* Initial beliefs and dietary constraints */
start.
tollerance(min, 0.85).
tollerance(max, 1.08).
diet_category_allowed(omnivore, dairy).
diet_category_allowed(omnivore, egg).
diet_category_allowed(omnivore, fish).
diet_category_allowed(omnivore, fruit).
diet_category_allowed(omnivore, grain).
diet_category_allowed(omnivore, legume).
diet_category_allowed(omnivore, nuts).
diet_category_allowed(omnivore, red_meat).
diet_category_allowed(omnivore, poultry).
diet_category_allowed(omnivore, vegetable).
diet_category_allowed(vegetarian, dairy).
diet_category_allowed(vegetarian, egg).
diet_category_allowed(vegetarian, fruit).
diet_category_allowed(vegetarian, grain).
diet_category_allowed(vegetarian, legume).
diet_category_allowed(vegetarian, nuts).
diet_category_allowed(vegetarian, vegetable).
diet_category_allowed(vegan, fruit).
diet_category_allowed(vegan, grain).
diet_category_allowed(vegan, legume).
diet_category_allowed(vegan, nuts).
diet_category_allowed(vegan, vegetable).

/* Candidate selection rules */
/* Define the template candidate rule. */
template_candidate(Slot, DietType, DailyTarget, Excluded, TargetProtein, TargetCarbs, TargetFat, Candidate) :-
        template_for_plan(Name, Calories, Protein, Carbs, Fat, RecipeSlot, Category) &
        slot_allowed(RecipeSlot, Slot) &
        diet_category_allowed(DietType, Category) &
        slot_weight(Slot, Weight) &
        tollerance(min, MinTol) &
        tollerance(max, MaxTol) &
        TargetCalories = DailyTarget * Weight &
        Name \== Excluded &
        Category \== Excluded &
        .check_macro_tolerance(Calories, Protein, Carbs, Fat, TargetCalories,
            TargetProtein, TargetCarbs, TargetFat, MinTol, MaxTol) &
        Candidate = candidate(Name, Calories, Protein, Carbs, Fat, Category).

/* Define the guided template candidate rule. */
guided_template_candidate(Slot, DietType, DailyTarget, Excluded, TargetProtein, TargetCarbs, TargetFat, RequiredCategory, Candidate) :-
        template_candidate(Slot, DietType, DailyTarget, Excluded,
            TargetProtein, TargetCarbs, TargetFat, Candidate) &
        Candidate = candidate(_, _, _, _, _, Category) &
        Category == RequiredCategory.

/* Agent lifecycle */
/* Start the agent. */
+!start : true <-
    .log("Chef Agent ready").

/* Runtime meal substitution */
/* Handle the choose runtime template goal. */
+!choose_runtime_template(Username, Date, MealType, PlannedRecipe, DietType, DailyTarget,
        TargetProtein, TargetCarbs, TargetFat)[source(_)] :
        template_candidate(MealType, DietType, DailyTarget, PlannedRecipe,
            TargetProtein, TargetCarbs, TargetFat,
            candidate(Name, Calories, Protein, Carbs, Fat, _)) <-
    .send("nutritionist@localhost", tell,
        template_candidate_response(Username, Date, MealType, Name, Calories, Protein, Carbs, Fat)).

/* Handle the choose runtime template goal. */
+!choose_runtime_template(Username, Date, MealType, PlannedRecipe, DietType, DailyTarget,
        TargetProtein, TargetCarbs, TargetFat)[source(_)] : true <-
    .send("nutritionist@localhost", tell, template_candidate_missing(Username, Date, MealType)).

/* Template-domain exchange with the Planner */
/* Handle the template domain request goal. */
+!template_domain_request(Username, Slot, DietType, DailyTarget, TargetProtein, TargetCarbs, TargetFat) :
        .findall(Candidate,
            template_candidate(Slot, DietType, DailyTarget, no_exclusion,
                TargetProtein, TargetCarbs, TargetFat, Candidate),
            Candidates) <-
    .log("Chef - returning complete template domain to Planner");
    !send_template_domain(Username, Slot, Candidates).

/* Handle the send template domain goal. */
+!send_template_domain(Username, Slot,
        [candidate(Name, Calories, Protein, Carbs, Fat, Category) | Rest]) : true <-
    .send("planner@localhost", tell,
        template_domain_candidate(Username, Slot, Name, Calories, Protein, Carbs, Fat, Category));
    !send_template_domain(Username, Slot, Rest).

/* Handle the send template domain goal. */
+!send_template_domain(Username, Slot, []) : true <-
    .send("planner@localhost", tell, template_domain_complete(Username, Slot)).

/* Template selection plans */
/* Handle the plan template request goal. */
+!plan_template_request(Username, Slot, DietType, DailyTarget, Mode, Excluded, TargetProtein, TargetCarbs, TargetFat, any) : true <-
    .log("Chef - no required category, using unguided template search");
    !plan_template_request(Username, Slot, DietType, DailyTarget, Mode, Excluded,
        TargetProtein, TargetCarbs, TargetFat).

/* Handle the plan template request goal. */
+!plan_template_request(Username, Slot, DietType, DailyTarget, strict, Excluded, TargetProtein, TargetCarbs, TargetFat, RequiredCategory) :
        RequiredCategory \== any &
        .findall(Candidate,
            guided_template_candidate(Slot, DietType, DailyTarget, Excluded,
                TargetProtein, TargetCarbs, TargetFat, RequiredCategory, Candidate),
            Candidates) &
        .random_candidate(Candidates, candidate(Name, Calories, Protein, Carbs, Fat, Category)) <-
    .log("Chef - selected guided macro-aware template in Jason");
    .send("planner@localhost", tell, plan_template_response(Username, Slot, Name, Calories, Protein, Carbs, Fat, Category)).

/* Handle the plan template request goal. */
+!plan_template_request(Username, Slot, DietType, DailyTarget, strict, Excluded, TargetProtein, TargetCarbs, TargetFat, RequiredCategory) :
        RequiredCategory \== any <-
    .log("Chef - no guided macro-aware template");
    .send("planner@localhost", tell, plan_template_failed(Username, Slot)).

/* Handle the plan template request goal. */
+!plan_template_request(Username, Slot, DietType, DailyTarget, Mode, Excluded, TargetProtein, TargetCarbs, TargetFat, RequiredCategory) :
        RequiredCategory \== any <-
    .log("Chef - unsupported guided template mode");
    .send("planner@localhost", tell, plan_template_failed(Username, Slot)).

/* Handle the plan template request goal. */
+!plan_template_request(Username, Slot, DietType, DailyTarget, strict, Excluded, TargetProtein, TargetCarbs, TargetFat) :
        .findall(Candidate,
            template_candidate(Slot, DietType, DailyTarget, Excluded,
                TargetProtein, TargetCarbs, TargetFat, Candidate),
            Candidates) &
        .random_candidate(Candidates, candidate(Name, Calories, Protein, Carbs, Fat, Category)) <-
    .log("Chef - selected randomized macro-aware template in Jason");
    .send("planner@localhost", tell, plan_template_response(Username, Slot, Name, Calories, Protein, Carbs, Fat, Category)).

/* Handle the plan template request goal. */
+!plan_template_request(Username, Slot, DietType, DailyTarget, Mode, Excluded, TargetProtein, TargetCarbs, TargetFat) : true <-
    .log("Chef - no Jason recipe match for Planner request");
    .send("planner@localhost", tell, plan_template_failed(Username, Slot)).
