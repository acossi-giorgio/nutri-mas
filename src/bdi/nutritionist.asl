/* Agent lifecycle and user-session setup */
start.
/* Start the agent. */
+!start : true <-
    .log("Nutritionist Agent ready").

/* Handle the init event. */
+init(Username)[source(_)] : true <-
    -init(Username);
    !set_active_session_user(Username);
    .concat("Nutritionist - identifying user: ", Username, LogMsg);
    .log(LogMsg);
    -user_profile(_, _, _, _, _);
    -daily_calories(_);
    -target_weight(_);
    -user_allergens(_);
    -user_goal(_);
    -diet_type(_);
    -culinary_preferences(_);
    -pending_height(_);
    -pending_weight(_);
    -pending_age(_);
    -pending_sex(_);
    -pending_activity(_);
    -pending_allergens(_);
    -pending_diet_type(_);
    -pending_culinary_preferences(_);
    !load_user_profile_from_beliefs(Username);
    !check_user_profile(Username).

/* Handle the set active session user goal. */
+!set_active_session_user(Username) : active_session_user(Previous) <-
    -active_session_user(Previous);
    +active_session_user(Username).

/* Handle the set active session user goal. */
+!set_active_session_user(Username) : true <-
    +active_session_user(Username).

/* Handle the load user profile from beliefs goal. */
+!load_user_profile_from_beliefs(Username) : user_profile_row(Username, Height, Weight, Age, Sex, Activity, _, _, Allergens, Goal, DietType, CulinaryPreferences) <-
    .calculate_profile_targets(Height, Weight, Age, Sex, Activity, Daily, RecalculatedGoal, TargetWeight);
    +user_profile(Height, Weight, Age, Sex, Activity);
    +daily_calories(Daily);
    +target_weight(TargetWeight);
    +user_allergens(Allergens);
    +user_goal(RecalculatedGoal);
    +diet_type(DietType);
    +culinary_preferences(CulinaryPreferences);
    -user_profile_row(Username, Height, Weight, Age, Sex, Activity, _, _, Allergens, Goal, DietType, CulinaryPreferences);
    +user_profile_row(Username, Height, Weight, Age, Sex, Activity, Daily, TargetWeight, Allergens, RecalculatedGoal, DietType, CulinaryPreferences);
    .log("Nutritionist - user profile loaded from CSV beliefs").

/* Handle the load user profile from beliefs goal. */
+!load_user_profile_from_beliefs(_) : true <- true.

/* Handle the check user profile goal. */
+!check_user_profile(Username) : user_profile(_, _, _, _, _) & daily_calories(Daily) & user_goal(Goal) & target_weight(TargetWeight) <-
    .log("Nutritionist - user profile already loaded");
    .send("gateway@localhost", tell, welcome_back(Daily, Goal, TargetWeight)).

/* Handle the check user profile goal. */
+!check_user_profile(Username) : true <-
    .log("Nutritionist - no user profile found, starting collection");
    !collect_user_profile.

/* Handle the collect user profile goal. */
+!collect_user_profile <-
    .log("Nutritionist - asking for height");
    .send("gateway@localhost", tell, ask(height)).

/* Profile and weight updates */
/* Handle the record weight belief goal. */
+!record_weight_belief(Username, Weight) :
        current_date(Today) & weight_log_entry(Username, Today, OldWeight) <-
    -weight_log_entry(Username, Today, OldWeight);
    +weight_log_entry(Username, Today, Weight).

/* Handle the record weight belief goal. */
+!record_weight_belief(Username, Weight) : current_date(Today) <-
    +weight_log_entry(Username, Today, Weight).

/* Handle the record weight belief goal. */
+!record_weight_belief(Username, Weight) : true <-
    +weight_log_entry(Username, "unknown", Weight).

/* Handle the update weight event. */
+update_weight(Username, NewWeight)[source(_)] :
        user_profile_row(Username, Height, PreviousWeight, Age, Sex, Activity, Daily, TargetWeight, Allergens, Goal, DietType, CulinaryPreferences) <-
    -update_weight(Username, NewWeight);
    .concat("Nutritionist - weight updated to ", NewWeight, LogMsg);
    .log(LogMsg);
    !record_weight_belief(Username, NewWeight);
    !handle_weight_update(Username, Height, PreviousWeight, NewWeight, Age, Sex, Activity, Daily, TargetWeight, Allergens, Goal, DietType, CulinaryPreferences).

/* Handle the handle weight update goal. */
+!handle_weight_update(Username, Height, _, NewWeight, Age, Sex, Activity, _, TargetWeight, Allergens, lose, DietType, CulinaryPreferences) :
        NewWeight <= TargetWeight <-
    !enter_weight_maintenance(Username, Height, NewWeight, Age, Sex, Activity, Allergens, TargetWeight, DietType, CulinaryPreferences).

/* Handle the handle weight update goal. */
+!handle_weight_update(Username, Height, _, NewWeight, Age, Sex, Activity, _, TargetWeight, Allergens, gain, DietType, CulinaryPreferences) :
        NewWeight >= TargetWeight <-
    !enter_weight_maintenance(Username, Height, NewWeight, Age, Sex, Activity, Allergens, TargetWeight, DietType, CulinaryPreferences).

/* Handle the handle weight update goal. */
+!handle_weight_update(Username, Height, PreviousWeight, NewWeight, Age, Sex, Activity, Daily, TargetWeight, Allergens, Goal, DietType, CulinaryPreferences) : true <-
    .calculate_weight_change_percent(PreviousWeight, NewWeight, ChangePercent);
    !apply_weight_change(Username, Height, NewWeight, Age, Sex, Activity, Daily, TargetWeight, Allergens, Goal, DietType, CulinaryPreferences, ChangePercent).

/* Handle the apply weight change goal. */
+!apply_weight_change(Username, Height, NewWeight, Age, Sex, Activity, _, _, Allergens, Goal, DietType, CulinaryPreferences, ChangePercent) :
        ChangePercent >= 1 <-
    .calculate_profile_targets_for_goal(Height, NewWeight, Age, Sex, Activity, Goal, NewDaily, NewTargetWeight);
    -user_profile(_, _, _, _, _);
    -daily_calories(_);
    -target_weight(_);
    +user_profile(Height, NewWeight, Age, Sex, Activity);
    +daily_calories(NewDaily);
    +target_weight(NewTargetWeight);
    -user_profile_row(Username, _, _, _, _, _, _, _, _, _, _, _);
    +user_profile_row(Username, Height, NewWeight, Age, Sex, Activity, NewDaily, NewTargetWeight, Allergens, Goal, DietType, CulinaryPreferences);
    .send("gateway@localhost", tell, weight_plan_rebalanced(NewWeight, ChangePercent, NewDaily, Goal));
    !refresh_week_plan(Username).

/* Handle the apply weight change goal. */
+!apply_weight_change(Username, Height, NewWeight, Age, Sex, Activity, Daily, TargetWeight, Allergens, Goal, DietType, CulinaryPreferences, ChangePercent) : true <-
    -user_profile(Height, _, Age, Sex, Activity);
    +user_profile(Height, NewWeight, Age, Sex, Activity);
    -user_profile_row(Username, _, _, _, _, _, _, _, _, _, _, _);
    +user_profile_row(Username, Height, NewWeight, Age, Sex, Activity, Daily, TargetWeight, Allergens, Goal, DietType, CulinaryPreferences);
    .send("gateway@localhost", tell, weight_change_recorded(NewWeight, ChangePercent)).

/* Handle the enter weight maintenance goal. */
+!enter_weight_maintenance(Username, Height, NewWeight, Age, Sex, Activity, Allergens, _, DietType, CulinaryPreferences) : true <-
    .calculate_profile_targets_for_goal(Height, NewWeight, Age, Sex, Activity, maintain, Daily, TargetWeight);
    -user_profile(_, _, _, _, _);
    -daily_calories(_);
    -user_allergens(_);
    -target_weight(_);
    -user_goal(_);
    +user_profile(Height, NewWeight, Age, Sex, Activity);
    +daily_calories(Daily);
    +target_weight(TargetWeight);
    +user_goal(maintain);
    +user_allergens(Allergens);
    -user_profile_row(Username, _, _, _, _, _, _, _, _, _, _, _);
    +user_profile_row(Username, Height, NewWeight, Age, Sex, Activity, Daily, TargetWeight, Allergens, maintain, DietType, CulinaryPreferences);
    .send("gateway@localhost", tell, target_weight_reached(NewWeight, Daily));
    !refresh_week_plan(Username).

/* Preferences and weekly-plan refresh */
/* Handle the update preferences event. */
+update_preferences(Username, DietType)[source(_)] :
        user_profile_row(Username, Height, Weight, Age, Sex, Activity, Daily, TargetWeight, Allergens, Goal, _, CulinaryPreferences) <-
    -update_preferences(Username, DietType);
    -pending_diet_type(_);
    -diet_type(_);
    +diet_type(DietType);
    -user_profile_row(Username, _, _, _, _, _, _, _, _, _, _, _);
    +user_profile_row(Username, Height, Weight, Age, Sex, Activity, Daily, TargetWeight, Allergens, Goal, DietType, CulinaryPreferences);
    .send("gateway@localhost", tell, preferences_updated(DietType));
    !refresh_week_plan(Username).

/* Handle the update culinary preferences event. */
+update_culinary_preferences(Username, CulinaryPreferences)[source(_)] :
        user_profile_row(Username, Height, Weight, Age, Sex, Activity, Daily, TargetWeight, Allergens, Goal, DietType, _) <-
    -update_culinary_preferences(Username, CulinaryPreferences);
    -culinary_preferences(_);
    +culinary_preferences(CulinaryPreferences);
    -user_profile_row(Username, _, _, _, _, _, _, _, _, _, _, _);
    +user_profile_row(Username, Height, Weight, Age, Sex, Activity, Daily, TargetWeight, Allergens, Goal, DietType, CulinaryPreferences);
    .send("gateway@localhost", tell, culinary_preferences_updated(CulinaryPreferences));
    !refresh_week_plan(Username).

/* Handle the refresh week plan goal. */
+!refresh_week_plan(Username) : daily_calories(Daily) & diet_type(DietType) & user_profile(_, Weight, _, _, Activity) & user_allergens(Allergens) <-
    .log("Nutritionist - refreshing weekly plan after profile/preference update");
    .send("gateway@localhost", tell, planning_started(Username));
    .send("planner@localhost", achieve, build_week_plan(Username, DietType, Daily, Weight, Activity, Allergens)).

/* Handle the refresh week plan goal. */
+!refresh_week_plan(Username) : daily_calories(Daily) & user_profile(_, Weight, _, _, Activity) & user_allergens(Allergens) <-
    .log("Nutritionist - refreshing weekly plan after profile/preference update");
    .send("gateway@localhost", tell, planning_started(Username));
    .send("planner@localhost", achieve, build_week_plan(Username, "omnivore", Daily, Weight, Activity, Allergens)).

/* Handle the build week plan event. */
+build_week_plan(Username)[source(_)] : true <-
    -build_week_plan(Username);
    .log("Nutritionist - manual week plan refresh requested");
    !refresh_week_plan(Username).

/* Handle the get user nutrition context goal. */
+!get_user_nutrition_context(Username)[source(_)] : true <-
    .log("Nutritionist - Cook requested user nutrition context");
    .send_user_nutrition_context(Username).

/* Profile onboarding */
/* Handle the answer event. */
+answer(Username, height, H)[source(_)] : true <-
    -answer(Username, height, H);
    +pending_height(H);
    .send("gateway@localhost", tell, ask(weight)).

/* Handle the answer event. */
+answer(Username, weight, W)[source(_)] : true <-
    -answer(Username, weight, W);
    +pending_weight(W);
    .send("gateway@localhost", tell, ask(age)).

/* Handle the answer event. */
+answer(Username, age, A)[source(_)] : true <-
    -answer(Username, age, A);
    +pending_age(A);
    .send("gateway@localhost", tell, ask(sex)).

/* Handle the answer event. */
+answer(Username, sex, S)[source(_)] : true <-
    -answer(Username, sex, S);
    +pending_sex(S);
    .send("gateway@localhost", tell, ask(activity)).

/* Handle the answer event. */
+answer(Username, activity, Act)[source(_)] :
        pending_height(H) & pending_weight(W) & pending_age(A) & pending_sex(S) <-
    -answer(Username, activity, Act);
    +pending_activity(Act);
    .send("gateway@localhost", tell, ask(allergens)).

/* Handle the answer event. */
+answer(Username, allergens, All)[source(_)] :
        pending_height(H) & pending_weight(W) & pending_age(A) &
        pending_sex(S) & pending_activity(Act) <-
    -answer(Username, allergens, All);
    +pending_allergens(All);
    -pending_height(H);
    -pending_weight(W);
    -pending_age(A);
    -pending_sex(S);
    -pending_activity(Act);
    -pending_allergens(All);
    +user_profile(H, W, A, S, Act);
    +user_allergens(All);
    .log("Nutritionist - all fields collected, computing profile");
    !compute_and_save_profile(H, W, A, S, Act, All).

/* Handle the compute and save profile goal. */
+!compute_and_save_profile(Height, Weight, Age, Sex, Activity, Allergens) : true <-
    .calculate_profile_targets(Height, Weight, Age, Sex, Activity, Daily, Goal, TargetWeight);
    +daily_calories(Daily);
    +target_weight(TargetWeight);
    +user_goal(Goal);
    .log("Nutritionist - daily calorie target computed");
    !collect_preferences.

/* Handle the collect preferences goal. */
+!collect_preferences <-
    .log("Nutritionist - asking diet type");
    .send("gateway@localhost", tell, ask(diet_type)).

/* Handle the answer event. */
+answer(Username, diet_type, DietType)[source(_)] :
        daily_calories(Daily) & user_goal(Goal) & user_allergens(Allergens) <-
    -answer(Username, diet_type, DietType);
    +pending_diet_type(DietType);
    .log("Nutritionist - diet type collected");
    .send("gateway@localhost", tell, ask(culinary_preferences)).

/* Handle the answer event. */
+answer(Username, culinary_preferences, CulinaryPreferences)[source(_)] :
        pending_diet_type(_) & daily_calories(_) & user_allergens(_) <-
    -answer(Username, culinary_preferences, CulinaryPreferences);
    +pending_culinary_preferences(CulinaryPreferences);
    .log("Nutritionist - culinary preferences collected");
    !finish_preferences(Username).

/* Handle the finish preferences goal. */
+!finish_preferences(Username) :
        pending_diet_type(DietType) &
        pending_culinary_preferences(CulinaryPreferences) &
        user_profile(Height, Weight, Age, Sex, Activity) &
        daily_calories(Daily) & user_goal(Goal) & target_weight(TargetWeight) &
        user_allergens(Allergens) <-
    -pending_diet_type(DietType);
    -pending_culinary_preferences(CulinaryPreferences);
    .log("Nutritionist - all preferences collected, triggering plan");
    -diet_type(_);
    +diet_type(DietType);
    -culinary_preferences(_);
    +culinary_preferences(CulinaryPreferences);
    -user_profile_row(Username, _, _, _, _, _, _, _, _, _, _, _);
    +user_profile_row(Username, Height, Weight, Age, Sex, Activity, Daily, TargetWeight, Allergens, Goal, DietType, CulinaryPreferences);
    .send("gateway@localhost", tell, profile_complete(Daily, Goal, TargetWeight));
    .send("gateway@localhost", tell, planning_started(Username));
    .send("planner@localhost", achieve, build_week_plan(Username, DietType, Daily, Weight, Activity, Allergens)).

/* Plan synchronization and history queries */
/* Handle the weekly plan displayed event. */
+weekly_plan_displayed(Username)[source(_)] : true <-
    -weekly_plan_displayed(Username);
    .send("gateway@localhost", tell, meal_tracking_started).

/* Handle the clear slot macro target row goal. */
+!clear_slot_macro_target_row(Username, Day, MealType) :
        slot_macro_target_row(Username, Day, MealType, TargetCalories, TargetProtein, TargetCarbs, TargetFat) <-
    -slot_macro_target_row(Username, Day, MealType, TargetCalories, TargetProtein, TargetCarbs, TargetFat);
    !clear_slot_macro_target_row(Username, Day, MealType).

/* Handle the clear slot macro target row goal. */
+!clear_slot_macro_target_row(_, _, _) : true <- true.

/* Handle the slot macro target event. */
+slot_macro_target(Username, Day, MealType, TargetCalories, TargetProtein, TargetCarbs, TargetFat)[source(_)] : true <-
    -slot_macro_target(Username, Day, MealType, TargetCalories, TargetProtein, TargetCarbs, TargetFat);
    !clear_slot_macro_target_row(Username, Day, MealType);
    +slot_macro_target_row(Username, Day, MealType, TargetCalories, TargetProtein, TargetCarbs, TargetFat).

/* Handle the get meal logs goal. */
+!get_meal_logs(Username)[source(_)] : true <-
    .send_meal_logs(Username).

/* Handle the get weight logs goal. */
+!get_weight_logs(Username)[source(_)] : true <-
    .send_weight_logs(Username).

/* Meal confirmation, substitution, and rebalancing */
/* Handle the confirm meal event. */
+confirm_meal(Username, MealType)[source(_)] :
        current_date(Today) &
        meal_log_row(Username, Today, Weekday, MealType, Planned, Actual, Status,
            PlannedCalories, PlannedProtein, PlannedCarbs, PlannedFat,
            Calories, Protein, Carbs, Fat, Source, ForecastedAt, ConfirmationRequestedAt, UpdatedAt) <-
    -confirm_meal(Username, MealType);
    -meal_log_row(Username, Today, Weekday, MealType, Planned, Actual, Status,
        PlannedCalories, PlannedProtein, PlannedCarbs, PlannedFat,
        Calories, Protein, Carbs, Fat, Source, ForecastedAt, ConfirmationRequestedAt, UpdatedAt);
    +meal_log_row(Username, Today, Weekday, MealType, Planned, Planned, "confirmed",
        PlannedCalories, PlannedProtein, PlannedCarbs, PlannedFat,
        PlannedCalories, PlannedProtein, PlannedCarbs, PlannedFat, "user", ForecastedAt, ConfirmationRequestedAt, "bdi");
    .send("gateway@localhost", tell, meal_status_updated(MealType, "confirmed")).

/* Handle the confirm meal event. */
+confirm_meal(Username, MealType)[source(_)] : current_date(Today) <-
    -confirm_meal(Username, MealType);
    .send("gateway@localhost", tell, meal_status_missing(Today, MealType)).

/* Handle the change planned meal event. */
+change_planned_meal(Username, Date, MealType, Intent)[source(_)] :
        meal_log_row(Username, Date, Weekday, MealType, Planned, Actual, Status,
            PlannedCalories, PlannedProtein, PlannedCarbs, PlannedFat,
            Calories, Protein, Carbs, Fat, Source, ForecastedAt, ConfirmationRequestedAt, UpdatedAt) <-
    -change_planned_meal(Username, Date, MealType, Intent);
    .send("chef@localhost", achieve,
        choose_runtime_template(Username, Date, MealType, Planned)).

/* Handle the change planned meal event. */
+change_planned_meal(Username, Date, MealType, Intent)[source(_)] : true <-
    -change_planned_meal(Username, Date, MealType, Intent);
    .send("gateway@localhost", tell, meal_status_missing(Date, MealType)).

/* Handle the template candidate response event. */
+template_candidate_response(Username, Date, MealType, Template, Calories, Protein, Carbs, Fat)[source(_)] :
        meal_log_row(Username, Date, Weekday, MealType, Planned, Actual, Status,
            PlannedCalories, PlannedProtein, PlannedCarbs, PlannedFat,
            OldCalories, OldProtein, OldCarbs, OldFat, Source, ForecastedAt, ConfirmationRequestedAt, UpdatedAt) <-
    -template_candidate_response(Username, Date, MealType, Template, Calories, Protein, Carbs, Fat);
    .send("planner@localhost", achieve,
        prepare_runtime_recipe(Username, Date, Weekday, MealType, Template, Calories, Protein, Carbs, Fat, "user_alternative")).

/* Handle the template candidate missing event. */
+template_candidate_missing(Username, Date, MealType)[source(_)] : true <-
    -template_candidate_missing(Username, Date, MealType);
    .send("gateway@localhost", tell, meal_status_missing(Date, MealType)).

/* Handle the runtime recipe response event. */
+runtime_recipe_response(Username, Date, MealType, Template, RecipeName, Calories, Protein, Carbs, Fat)[source(_)] :
        meal_log_row(Username, Date, Weekday, MealType, Planned, Actual, Status,
            PlannedCalories, PlannedProtein, PlannedCarbs, PlannedFat,
            OldCalories, OldProtein, OldCarbs, OldFat, Source, ForecastedAt, ConfirmationRequestedAt, UpdatedAt) <-
    -runtime_recipe_response(Username, Date, MealType, Template, RecipeName, Calories, Protein, Carbs, Fat);
    !apply_meal_update(Username, Date, MealType, RecipeName, Calories, Protein, Carbs, Fat, "user_prepared");
    !maybe_rebalance_after_update(Username, Date, MealType).

/* Handle the runtime recipe failed event. */
+runtime_recipe_failed(Username, Date, MealType)[source(_)] : true <-
    -runtime_recipe_failed(Username, Date, MealType);
    .log("Nutritionist - runtime alternative failed, notifying user.");
    .send("gateway@localhost", tell, runtime_alternative_failed(Username, Date, MealType));
    .send("gateway@localhost", tell, meal_status_missing(Date, MealType)).

/* Handle the apply meal update goal. */
+!apply_meal_update(Username, Date, MealType, RecipeName, Calories, Protein, Carbs, Fat, NewSource) :
        meal_log_row(Username, Date, Weekday, MealType, Planned, Actual, Status,
            PlannedCalories, PlannedProtein, PlannedCarbs, PlannedFat,
            OldCalories, OldProtein, OldCarbs, OldFat, Source, ForecastedAt, ConfirmationRequestedAt, UpdatedAt) <-
    -meal_log_row(Username, Date, Weekday, MealType, Planned, Actual, Status,
        PlannedCalories, PlannedProtein, PlannedCarbs, PlannedFat,
        OldCalories, OldProtein, OldCarbs, OldFat, Source, ForecastedAt, ConfirmationRequestedAt, UpdatedAt);
    +meal_log_row(Username, Date, Weekday, MealType, Planned, RecipeName, "modified",
        PlannedCalories, PlannedProtein, PlannedCarbs, PlannedFat,
        Calories, Protein, Carbs, Fat, NewSource, ForecastedAt, ConfirmationRequestedAt, "bdi").

/* Handle the apply meal update goal. */
+!apply_meal_update(_, _, _, _, _, _, _, _, _) : true <- true.

/* Handle the maybe rebalance after update goal. */
+!maybe_rebalance_after_update(Username, Date, MealType) : true <-
    !request_rebalance_after(Username, Date, MealType).

/* Handle the request rebalance after goal. */
+!request_rebalance_after(Username, Date, Slot) : true <-
    -+pending_rebalances(Username, Date, 0);
    -pending_rebalance_origin(Username, Date, _);
    +pending_rebalance_origin(Username, Date, Slot);
    !do_request_rebalance_after(Username, Date, Slot).

/* Handle the do request rebalance after goal. */
+!do_request_rebalance_after(Username, Date, Slot) : next_meal_slot(Slot, NextSlot) <-
    !request_rebalance_slot(Username, Date, NextSlot);
    !do_request_rebalance_after(Username, Date, NextSlot).

/* Handle the do request rebalance after goal. */
+!do_request_rebalance_after(Username, Date, Slot) :
        not next_meal_slot(Slot, _) &
        pending_rebalances(Username, Date, Count) &
        Count == 0 <-
    -pending_rebalances(Username, Date, 0);
    -pending_rebalance_origin(Username, Date, _);
    !get_rebalanced_current_plan(Username).

/* Handle the do request rebalance after goal. */
+!do_request_rebalance_after(_, _, _) : true <- true.

/* Handle the get eaten today goal. */
+!get_eaten_today(Username, Date, Eaten) : true <-
    .calculate_eaten_today_from_log(Username, Date, Eaten).

/* Handle the request rebalance slot goal. */
+!request_rebalance_slot(Username, Date, Slot) :
        meal_log_row(Username, Date, Weekday, Slot, Planned, Actual, "forecasted",
            PlannedCalories, PlannedProtein, PlannedCarbs, PlannedFat,
            Calories, Protein, Carbs, Fat, Source, ForecastedAt, ConfirmationRequestedAt, UpdatedAt) &
        daily_calories(Daily) & slot_weight(Slot, Weight) &
        diet_type(DietType) &
        pending_rebalances(Username, Date, CurrentCount) &
        pending_rebalance_origin(Username, Date, OriginSlot) <-
    -+pending_rebalances(Username, Date, CurrentCount + 1);
    !get_eaten_today(Username, Date, EatenToday);
    .calculate_rebalance_slot_target(Daily, EatenToday, OriginSlot, Slot, TargetCalories);
    .send("planner@localhost", achieve, rebalance_slot(Username, Date, Weekday, Slot, DietType, TargetCalories, Planned)).

/* Handle the request rebalance slot goal. */
+!request_rebalance_slot(_, _, _) : true <- true.

/* Handle the rebalance recipe response event. */
+rebalance_recipe_response(Username, Date, MealType, Template, RecipeName, Calories, Protein, Carbs, Fat)[source(_)] :
        meal_log_row(Username, Date, Weekday, MealType, Planned, Actual, "forecasted",
            PlannedCalories, PlannedProtein, PlannedCarbs, PlannedFat,
            OldCalories, OldProtein, OldCarbs, OldFat, Source, ForecastedAt, ConfirmationRequestedAt, UpdatedAt) <-
    -rebalance_recipe_response(Username, Date, MealType, Template, RecipeName, Calories, Protein, Carbs, Fat);
    -meal_log_row(Username, Date, Weekday, MealType, Planned, Actual, "forecasted",
        PlannedCalories, PlannedProtein, PlannedCarbs, PlannedFat,
        OldCalories, OldProtein, OldCarbs, OldFat, Source, ForecastedAt, ConfirmationRequestedAt, UpdatedAt);
    +meal_log_row(Username, Date, Weekday, MealType, RecipeName, "", "forecasted",
        Calories, Protein, Carbs, Fat, Calories, Protein, Carbs, Fat, "rebalance_prepared", ForecastedAt, "", "bdi");
    !decrement_pending_rebalances(Username, Date).

/* Handle the rebalance recipe failed event. */
+rebalance_recipe_failed(Username, Date, MealType)[source(_)] : true <-
    -rebalance_recipe_failed(Username, Date, MealType);
    .log("Nutritionist - rebalance failed, notifying user.");
    .send("gateway@localhost", tell, rebalance_failed(Username, Date, MealType));
    !decrement_pending_rebalances(Username, Date).

/* Handle the rebalance template failed event. */
+rebalance_template_failed(Username, Date, MealType)[source(_)] : true <-
    -rebalance_template_failed(Username, Date, MealType);
    .log("Nutritionist - no rebalance recipe found, notifying user.");
    .send("gateway@localhost", tell, rebalance_failed(Username, Date, MealType));
    !decrement_pending_rebalances(Username, Date).

/* Handle the decrement pending rebalances goal. */
+!decrement_pending_rebalances(Username, Date) :
        pending_rebalances(Username, Date, Count) & Count > 1 <-
    -+pending_rebalances(Username, Date, Count - 1).

/* Handle the decrement pending rebalances goal. */
+!decrement_pending_rebalances(Username, Date) :
        pending_rebalances(Username, Date, Count) & Count == 1 <-
    -pending_rebalances(Username, Date, 1);
    -pending_rebalance_origin(Username, Date, _);
    !get_rebalanced_current_plan(Username).

/* Handle the get current plan goal. */
+!get_current_plan(Username) : current_date(Today) <-
    !ensure_daily_forecasts(Username, Today);
    .send_daily_plan_payload(Username, Today, current).

/* Handle the get rebalanced current plan goal. */
+!get_rebalanced_current_plan(Username) : current_date(Today) <-
    !ensure_daily_forecasts(Username, Today);
    .send_daily_plan_payload(Username, Today, rebalanced).

/* Handle the ensure daily forecasts goal. */
+!ensure_daily_forecasts(Username, Today) :
        current_weekday(Weekday) <-
    !create_daily_forecast(Username, Today, Weekday).

/* Handle the ensure daily forecasts goal. */
+!ensure_daily_forecasts(_, _) : true <- true.

/* The first tick establishes a baseline; earlier meal times are not replayed. */
/* Clock-driven forecasts and reminders */
/* Handle the clock tick event. */
+clock_tick(Date, Weekday, Hour, Minute, NowMinutes)[source(_)] :
        not last_clock_tick(_, _) <-
    -clock_tick(Date, Weekday, Hour, Minute, NowMinutes);
    +last_clock_tick(Date, NowMinutes);
    !set_current_weekday(Weekday);
    !ensure_active_daily_forecast(Date, Weekday).

/* Normal ticks evaluate only meal times crossed since the previous tick. */
/* Handle the clock tick event. */
+clock_tick(Date, Weekday, Hour, Minute, NowMinutes)[source(_)] :
        last_clock_tick(Date, PreviousMinutes) &
        NowMinutes >= PreviousMinutes <-
    -clock_tick(Date, Weekday, Hour, Minute, NowMinutes);
    -last_clock_tick(Date, PreviousMinutes);
    +last_clock_tick(Date, NowMinutes);
    !set_current_weekday(Weekday);
    !ensure_active_daily_forecast(Date, Weekday);
    !evaluate_crossed_meals(Date, Weekday, PreviousMinutes, NowMinutes).

/* A new day or a backward clock jump starts a new baseline. */
/* Handle the clock tick event. */
+clock_tick(Date, Weekday, Hour, Minute, NowMinutes)[source(_)] :
        last_clock_tick(PreviousDate, PreviousMinutes) <-
    -clock_tick(Date, Weekday, Hour, Minute, NowMinutes);
    -last_clock_tick(PreviousDate, PreviousMinutes);
    +last_clock_tick(Date, NowMinutes);
    !set_current_weekday(Weekday);
    !ensure_active_daily_forecast(Date, Weekday).

/* Handle the set current weekday goal. */
+!set_current_weekday(Weekday) : current_weekday(Previous) <-
    -current_weekday(Previous);
    +current_weekday(Weekday).

/* Handle the set current weekday goal. */
+!set_current_weekday(Weekday) : true <-
    +current_weekday(Weekday).

/* Handle the ensure active daily forecast goal. */
+!ensure_active_daily_forecast(Date, Weekday) : active_session_user(Username) <-
    !create_daily_forecast(Username, Date, Weekday).

/* Handle the ensure active daily forecast goal. */
+!ensure_active_daily_forecast(_, _) : true <- true.

/* Handle the evaluate crossed meals goal. */
+!evaluate_crossed_meals(Date, Weekday, PreviousMinutes, NowMinutes) : true <-
    !evaluate_crossed_meal_from(Date, Weekday, PreviousMinutes, NowMinutes, breakfast).

/* Handle the evaluate crossed meal from goal. */
+!evaluate_crossed_meal_from(Date, Weekday, PreviousMinutes, NowMinutes, Slot) :
        meal_time(Slot, ScheduledMinutes) &
        PreviousMinutes < ScheduledMinutes &
        NowMinutes >= ScheduledMinutes <-
    !notify_crossed_meal(Date, Weekday, Slot);
    !evaluate_next_crossed_meal(Date, Weekday, PreviousMinutes, NowMinutes, Slot).

/* Handle the evaluate crossed meal from goal. */
+!evaluate_crossed_meal_from(Date, Weekday, PreviousMinutes, NowMinutes, Slot) : true <-
    !evaluate_next_crossed_meal(Date, Weekday, PreviousMinutes, NowMinutes, Slot).

/* Handle the evaluate next crossed meal goal. */
+!evaluate_next_crossed_meal(Date, Weekday, PreviousMinutes, NowMinutes, Slot) :
        next_meal_slot(Slot, NextSlot) <-
    !evaluate_crossed_meal_from(Date, Weekday, PreviousMinutes, NowMinutes, NextSlot).

/* Handle the evaluate next crossed meal goal. */
+!evaluate_next_crossed_meal(_, _, _, _, _) : true <- true.

/* Handle the notify crossed meal goal. */
+!notify_crossed_meal(Date, Weekday, Slot) :
        active_session_user(Username) &
        not pending_rebalances(Username, Date, _) &
        meal_log_row(Username, Date, Weekday, Slot, PlannedRecipe, Actual, "forecasted",
            PlannedCalories, PlannedProtein, PlannedCarbs, PlannedFat,
            Calories, Protein, Carbs, Fat, Source, ForecastedAt, "", UpdatedAt) <-
    -meal_log_row(Username, Date, Weekday, Slot, PlannedRecipe, Actual, "forecasted",
        PlannedCalories, PlannedProtein, PlannedCarbs, PlannedFat,
        Calories, Protein, Carbs, Fat, Source, ForecastedAt, "", UpdatedAt);
    +meal_log_row(Username, Date, Weekday, Slot, PlannedRecipe, Actual, "forecasted",
        PlannedCalories, PlannedProtein, PlannedCarbs, PlannedFat,
        Calories, Protein, Carbs, Fat, Source, ForecastedAt, "requested", "bdi");
    .send("gateway@localhost", tell,
        meal_confirmation_request(Username, Date, Weekday, Slot, PlannedRecipe)).

/* Handle the notify crossed meal goal. */
+!notify_crossed_meal(_, _, _) : true <- true.

/* Handle the create daily forecast goal. */
+!create_daily_forecast(Username, Date, Weekday) : true <-
    !create_daily_forecast_from(Username, Date, Weekday, breakfast).

/* Handle the create daily forecast from goal. */
+!create_daily_forecast_from(Username, Date, Weekday, Slot) : true <-
    !create_daily_forecast_slot(Username, Date, Weekday, Slot);
    !create_next_daily_forecast_slot(Username, Date, Weekday, Slot).

/* Handle the create next daily forecast slot goal. */
+!create_next_daily_forecast_slot(Username, Date, Weekday, Slot) : next_meal_slot(Slot, NextSlot) <-
    !create_daily_forecast_from(Username, Date, Weekday, NextSlot).

/* Handle the create next daily forecast slot goal. */
+!create_next_daily_forecast_slot(_, _, _, _) : true <- true.

/* Handle the create daily forecast slot goal. */
+!create_daily_forecast_slot(Username, Date, Weekday, Slot) :
        meal_log_row(Username, Date, Weekday, Slot, _, _, _, _, _, _, _, _, _, _, _, _, _, _, _) <-
    true.

/* Handle the create daily forecast slot goal. */
+!create_daily_forecast_slot(Username, Date, Weekday, Slot) :
        planned_dish_row(Username, Weekday, Slot, Dish, Calories, Protein, Carbs, Fat) <-
    +meal_log_row(Username, Date, Weekday, Slot, Dish, "", "forecasted",
        Calories, Protein, Carbs, Fat, Calories, Protein, Carbs, Fat, "plan", "bdi", "", "bdi").

/* Handle the create daily forecast slot goal. */
+!create_daily_forecast_slot(_, _, _, _) : true <- true.

/* Meal logging and nutrition summaries */
/* Handle the log meal event. */
+log_meal(Username, Slot, Name, Calories)[source(_)] : current_date(Today) <-
    -log_meal(Username, Slot, Name, Calories);
    .concat("Nutritionist - asking Cook to evaluate slotted free meal: ", Name, LogPrefix);
    .concat(LogPrefix, " for slot: ", LogPrefix2);
    .concat(LogPrefix2, Slot, LogMsg);
    .log(LogMsg);
    .send_free_meal_to_cook(Username, Today, Slot, Name, Calories).

/* Handle the free meal evaluated event. */
+free_meal_evaluated(Username, Date, Slot, Name, Calories, Protein, Carbs, Fat, Template)[source(_)] :
        meal_log_row(Username, Date, Weekday, Slot, Planned, Actual, Status,
            PlannedCalories, PlannedProtein, PlannedCarbs, PlannedFat,
            OldCalories, OldProtein, OldCarbs, OldFat, Source, ForecastedAt, ConfirmationRequestedAt, UpdatedAt) <-
    -free_meal_evaluated(Username, Date, Slot, Name, Calories, Protein, Carbs, Fat, Template);
    .log("Nutritionist - free meal for slot evaluated, replacing planned meal in the log...");
    -meal_log_row(Username, Date, Weekday, Slot, Planned, Actual, Status,
        PlannedCalories, PlannedProtein, PlannedCarbs, PlannedFat,
        OldCalories, OldProtein, OldCarbs, OldFat, Source, ForecastedAt, ConfirmationRequestedAt, UpdatedAt);
    +meal_log_row(Username, Date, Weekday, Slot, Planned, Name, "modified",
        PlannedCalories, PlannedProtein, PlannedCarbs, PlannedFat,
        Calories, Protein, Carbs, Fat, "user", ForecastedAt, ConfirmationRequestedAt, "bdi");
    !update_daily_recap(Username, Name, Calories);
    !update_weekly_eaten_total(Username, Calories, WeeklyTotal);
    !check_weekly_budget(Name, Calories, WeeklyTotal);
    .send("gateway@localhost", tell, meal_logged_rebalancing(Name, Calories));
    !maybe_rebalance_after_update(Username, Date, Slot).

/* Handle the free meal evaluated event. */
+free_meal_evaluated(Username, Date, Slot, Name, Calories, Protein, Carbs, Fat, Template)[source(_)] : true <-
    -free_meal_evaluated(Username, Date, Slot, Name, Calories, Protein, Carbs, Fat, Template);
    .log("Nutritionist - free meal evaluated without planned row, storing standalone log entry...");
    +meal_log_entry(Username, Date, Name, Calories, Protein, Carbs, Fat);
    +meal_log_row(Username, Date, "", Slot, "", Name, "confirmed",
        0, 0, 0, 0,
        Calories, Protein, Carbs, Fat, "user", "", "", "bdi");
    !update_daily_recap(Username, Name, Calories);
    !update_weekly_eaten_total(Username, Calories, WeeklyTotal);
    !check_weekly_budget(Name, Calories, WeeklyTotal);
    .send("gateway@localhost", tell, meal_logged_rebalancing(Name, Calories));
    !maybe_rebalance_after_update(Username, Date, Slot).

/* Handle the log meal calories event. */
+log_meal_calories(Username, Name, Calories)[source(_)] : true <-
    -log_meal_calories(Username, Name, Calories);
    !record_meal_entry(Username, Name, Calories);
    .send("gateway@localhost", tell, log_meal_ok(Name, Calories)).

/* Handle the remove meal event. */
+remove_meal(Username, Name)[source(_)] :
        current_date(Today) & meal_log_entry(Username, Today, Name, Calories, Protein, Carbs, Fat) <-
    -remove_meal(Username, Name);
    -meal_log_entry(Username, Today, Name, Calories, Protein, Carbs, Fat);
    !remove_meal_log_row_by_name(Username, Today, Name);
    !decrease_weekly_eaten_total(Username, Calories);
    !decrease_daily_recap(Username, Calories);
    !clear_daily_meals_text(Username);
    .send("gateway@localhost", tell, meal_removed(Name)).

/* Handle the remove meal event. */
+remove_meal(Username, Name)[source(_)] : true <-
    -remove_meal(Username, Name);
    .send("gateway@localhost", tell, meal_not_found(Name)).

/* Handle the remove meal log row by name goal. */
+!remove_meal_log_row_by_name(Username, Date, Name) :
        meal_log_row(Username, Date, Weekday, MealType, Planned, Name, Status,
            PlannedCalories, PlannedProtein, PlannedCarbs, PlannedFat,
            Calories, Protein, Carbs, Fat, Source, ForecastedAt, ConfirmationRequestedAt, UpdatedAt) <-
    -meal_log_row(Username, Date, Weekday, MealType, Planned, Name, Status,
        PlannedCalories, PlannedProtein, PlannedCarbs, PlannedFat,
        Calories, Protein, Carbs, Fat, Source, ForecastedAt, ConfirmationRequestedAt, UpdatedAt).

/* Handle the remove meal log row by name goal. */
+!remove_meal_log_row_by_name(_, _, _) : true <- true.

/* Handle the get daily recap goal. */
+!get_daily_recap(Username)[source(_)] : true <-
    .send_daily_recap_from_meal_log(Username).

/* Handle the record meal entry goal. */
+!record_meal_entry(Username, Name, Calories) : current_date(Today) <-
    +meal_log_entry(Username, Today, Name, Calories, 0, 0, 0);
    +meal_log_row(Username, Today, "", "logged", "", Name, "confirmed",
        Calories, 0, 0, 0, Calories, 0, 0, 0, "user", "", "", "bdi");
    !update_daily_recap(Username, Name, Calories).

/* Handle the update daily recap goal. */
+!update_daily_recap(Username, Name, Calories) :
        daily_eaten_total(Username, Previous) & daily_meals_text(Username, PreviousMeals) & PreviousMeals \== "" <-
    -daily_eaten_total(Username, Previous);
    -daily_meals_text(Username, PreviousMeals);
    Total = Previous + Calories;
    .concat(PreviousMeals, "|", Name, Meals);
    +daily_eaten_total(Username, Total);
    +daily_meals_text(Username, Meals).

/* Handle the update daily recap goal. */
+!update_daily_recap(Username, Name, Calories) :
        daily_eaten_total(Username, Previous) & daily_meals_text(Username, "") <-
    -daily_eaten_total(Username, Previous);
    -daily_meals_text(Username, "");
    Total = Previous + Calories;
    +daily_eaten_total(Username, Total);
    +daily_meals_text(Username, Name).

/* Handle the update daily recap goal. */
+!update_daily_recap(Username, Name, Calories) : true <-
    +daily_eaten_total(Username, Calories);
    +daily_meals_text(Username, Name).

/* Handle the decrease daily recap goal. */
+!decrease_daily_recap(Username, Calories) : daily_eaten_total(Username, Previous) <-
    -daily_eaten_total(Username, Previous);
    Total = Previous - Calories;
    +daily_eaten_total(Username, Total).

/* Handle the decrease daily recap goal. */
+!decrease_daily_recap(_, _) : true <- true.

/* Handle the clear daily meals text goal. */
+!clear_daily_meals_text(Username) : daily_meals_text(Username, Meals) <-
    -daily_meals_text(Username, Meals);
    +daily_meals_text(Username, "").

/* Handle the clear daily meals text goal. */
+!clear_daily_meals_text(_) : true <- true.

/* Handle the update weekly eaten total goal. */
+!update_weekly_eaten_total(Username, Calories, Total) : weekly_eaten_total(Username, Previous) <-
    -weekly_eaten_total(Username, Previous);
    Total = Previous + Calories;
    +weekly_eaten_total(Username, Total).

/* Handle the update weekly eaten total goal. */
+!update_weekly_eaten_total(Username, Calories, Calories) : true <-
    +weekly_eaten_total(Username, Calories).

/* Handle the decrease weekly eaten total goal. */
+!decrease_weekly_eaten_total(Username, Calories) : weekly_eaten_total(Username, Previous) <-
    -weekly_eaten_total(Username, Previous);
    Total = Previous - Calories;
    +weekly_eaten_total(Username, Total).

/* Handle the decrease weekly eaten total goal. */
+!decrease_weekly_eaten_total(_, _) : true <- true.

/* Handle the check weekly budget goal. */
+!check_weekly_budget(Name, Calories, WeeklyTotal) : daily_calories(DailyLimit) <-
    WeeklyBudget = DailyLimit * 7;
    !decide_weekly_warning(Name, Calories, WeeklyTotal, WeeklyBudget).

/* Handle the check weekly budget goal. */
+!check_weekly_budget(_, _, _) : true <- true.

/* Handle the decide weekly warning goal. */
+!decide_weekly_warning(_, _, WeeklyTotal, WeeklyBudget) :
        WeeklyTotal > WeeklyBudget <-
    .send("gateway@localhost", tell, weekly_budget_exceeded(WeeklyTotal, WeeklyBudget)).

/* Handle the decide weekly warning goal. */
+!decide_weekly_warning(_, _, _, _) : true <- true.

/* Persisted-plan cleanup */
/* Handle the clear planned dishes goal. */
+!clear_planned_dishes(Username) : true <-
    .log("Nutritionist - clearing active plan after the replacement is ready");
    !clear_nutritionist_planned_dishes(Username);
    !clear_nutritionist_planned_recipes(Username);
    !clear_nutritionist_forecasts(Username);
    .send("planner@localhost", tell, plan_storage_cleared(Username)).

/* Handle the clear nutritionist planned dishes goal. */
+!clear_nutritionist_planned_dishes(Username) : planned_dish_row(Username, D, S, Di, C, P, Ca, F) <-
    -planned_dish_row(Username, D, S, Di, C, P, Ca, F);
    !clear_nutritionist_planned_dishes(Username).

/* Handle the clear nutritionist planned dishes goal. */
+!clear_nutritionist_planned_dishes(_) : true <- true.

/* Handle the clear nutritionist planned recipes goal. */
+!clear_nutritionist_planned_recipes(Username) : planned_recipe_row(Username, D, S, Di, T, I, Ins, C, P, Ca, F) <-
    -planned_recipe_row(Username, D, S, Di, T, I, Ins, C, P, Ca, F);
    !clear_nutritionist_planned_recipes(Username).

/* Handle the clear nutritionist planned recipes goal. */
+!clear_nutritionist_planned_recipes(_) : true <- true.

/* Handle the clear nutritionist forecasts goal. */
+!clear_nutritionist_forecasts(Username) : meal_log_row(Username, Date, Weekday, Slot, Planned, Actual, "forecasted", PC, PP, PCa, PF, C, P, Ca, F, Src, FAt, CReq, UAt) <-
    -meal_log_row(Username, Date, Weekday, Slot, Planned, Actual, "forecasted", PC, PP, PCa, PF, C, P, Ca, F, Src, FAt, CReq, UAt);
    !clear_nutritionist_forecasts(Username).

/* Handle the clear nutritionist forecasts goal. */
+!clear_nutritionist_forecasts(_) : true <- true.
