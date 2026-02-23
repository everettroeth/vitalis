// ── Vitalis Type Definitions ──
// Mirrors backend Pydantic models from src/models/

// ── Enums ──

export enum HealthStatus {
  Thriving = "thriving",
  Watch = "watch",
  Concern = "concern",
  Unknown = "unknown",
}

export enum AccountType {
  Individual = "individual",
  Household = "household",
}

export enum SubscriptionTier {
  Free = "free",
  Pro = "pro",
  Family = "family",
}

export enum SubscriptionStatus {
  Active = "active",
  PastDue = "past_due",
  Cancelled = "cancelled",
  Trialing = "trialing",
}

export enum BiologicalSex {
  Male = "male",
  Female = "female",
}

export enum UserRole {
  Owner = "owner",
  Member = "member",
}

export enum BiomarkerCategory {
  Metabolic = "metabolic",
  Thyroid = "thyroid",
  Hormones = "hormones",
  Iron = "iron",
  Vitamins = "vitamins",
  Lipids = "lipids",
  Liver = "liver",
  Kidney = "kidney",
  Inflammation = "inflammation",
  CBC = "cbc",
  Cardiac = "cardiac",
  Other = "other",
}

export enum MarkerFlag {
  Normal = "normal",
  Low = "low",
  High = "high",
  Critical = "critical",
}

export enum GoalDirection {
  Minimize = "minimize",
  Maximize = "maximize",
  Target = "target",
}

export enum GoalMetricType {
  BloodMarker = "blood_marker",
  Measurement = "measurement",
  Wearable = "wearable",
  Custom = "custom",
}

export enum InsightType {
  Correlation = "correlation",
  Anomaly = "anomaly",
  Trend = "trend",
  GoalProgress = "goal_progress",
  Recommendation = "recommendation",
}

export enum DocumentType {
  BloodWork = "blood_work",
  Dexa = "dexa",
  Epigenetics = "epigenetics",
  Imaging = "imaging",
  DoctorNotes = "doctor_notes",
  Other = "other",
}

export enum ParseStatus {
  Pending = "pending",
  Processing = "processing",
  Completed = "completed",
  Failed = "failed",
  AwaitingConfirmation = "awaiting_confirmation",
}

export enum MeasurementMetric {
  Weight = "weight",
  BodyFatPercentage = "body_fat_percentage",
  WaistCircumference = "waist_circumference",
  HipCircumference = "hip_circumference",
  ChestCircumference = "chest_circumference",
  NeckCircumference = "neck_circumference",
  BicepCircumference = "bicep_circumference",
  ThighCircumference = "thigh_circumference",
  CalfCircumference = "calf_circumference",
  BloodPressureSystolic = "blood_pressure_systolic",
  BloodPressureDiastolic = "blood_pressure_diastolic",
  RestingHeartRate = "resting_heart_rate",
  BodyTemperature = "body_temperature",
  BloodGlucose = "blood_glucose",
  Height = "height",
  Custom = "custom",
}

export enum MenstrualPhase {
  Menstrual = "menstrual",
  Follicular = "follicular",
  Ovulation = "ovulation",
  Luteal = "luteal",
}

export enum MealType {
  Breakfast = "breakfast",
  Lunch = "lunch",
  Dinner = "dinner",
  Snack = "snack",
  Fasting = "fasting",
}

// ── Core Entity Types ──

export interface Account {
  id: string;
  account_type: AccountType;
  subscription_tier: SubscriptionTier;
  subscription_status: SubscriptionStatus;
  stripe_customer_id: string | null;
  max_members: number;
  created_at: string;
  updated_at: string;
}

export interface User {
  id: string;
  account_id: string;
  clerk_user_id: string;
  email: string;
  display_name: string;
  first_name: string | null;
  last_name: string | null;
  avatar_url: string | null;
  date_of_birth: string | null;
  biological_sex: BiologicalSex | null;
  role: UserRole;
  timezone: string;
  created_at: string;
  updated_at: string;
}

export interface UserPreferences {
  id: string;
  user_id: string;
  unit_system: "imperial" | "metric";
  weight_unit: "lbs" | "kg";
  height_unit: "in" | "cm";
  temperature_unit: "F" | "C";
  date_format: string;
  time_format: "12h" | "24h";
  theme: "light" | "dark" | "system";
  notifications_enabled: boolean;
  daily_reminder_time: string | null;
}

// ── Wearable Types ──

export interface ConnectedDevice {
  id: string;
  user_id: string;
  source: string;
  device_name: string | null;
  is_active: boolean;
  last_sync_at: string | null;
  sync_status: string | null;
  created_at: string;
}

export interface WearableDaily {
  id: string;
  user_id: string;
  source: string;
  date: string;
  resting_heart_rate: number | null;
  avg_heart_rate: number | null;
  max_heart_rate: number | null;
  hrv_rmssd: number | null;
  hrv_avg: number | null;
  steps: number | null;
  active_calories: number | null;
  total_calories: number | null;
  active_minutes: number | null;
  spo2_avg: number | null;
  respiratory_rate: number | null;
  stress_avg: number | null;
  body_battery_high: number | null;
  body_battery_low: number | null;
  vo2_max: number | null;
  readiness_score: number | null;
  created_at: string;
}

export interface SleepSession {
  id: string;
  user_id: string;
  source: string;
  date: string;
  sleep_start: string;
  sleep_end: string;
  total_sleep_minutes: number | null;
  rem_minutes: number | null;
  deep_minutes: number | null;
  light_minutes: number | null;
  awake_minutes: number | null;
  sleep_score: number | null;
  sleep_efficiency: number | null;
  avg_hr_sleep: number | null;
  avg_hrv_sleep: number | null;
  avg_respiratory_rate: number | null;
  avg_spo2_sleep: number | null;
  hypnogram: number[] | null;
  created_at: string;
}

export interface WearableActivity {
  id: string;
  user_id: string;
  source: string;
  activity_type: string;
  started_at: string;
  ended_at: string | null;
  duration_minutes: number | null;
  distance_meters: number | null;
  calories_burned: number | null;
  avg_heart_rate: number | null;
  max_heart_rate: number | null;
  avg_pace_seconds: number | null;
  elevation_gain_meters: number | null;
  training_effect_aerobic: number | null;
  training_effect_anaerobic: number | null;
  training_load: number | null;
  created_at: string;
}

// ── Blood Work Types ──

export interface BiomarkerDictionary {
  id: string;
  canonical_name: string;
  display_name: string;
  category: BiomarkerCategory;
  unit: string;
  loinc_code: string | null;
  description: string | null;
  aliases: string[];
}

export interface BloodPanel {
  id: string;
  user_id: string;
  panel_date: string;
  lab_name: string | null;
  provider_name: string | null;
  document_id: string | null;
  notes: string | null;
  created_at: string;
}

export interface BloodMarker {
  id: string;
  panel_id: string;
  biomarker_id: string;
  raw_name: string | null;
  raw_value: string | null;
  canonical_value: number | null;
  unit: string | null;
  reference_range_low: number | null;
  reference_range_high: number | null;
  flag: MarkerFlag;
  parse_confidence: number | null;
  biomarker: BiomarkerDictionary | null;
  created_at: string;
}

// ── Body Composition Types ──

export interface DexaScan {
  id: string;
  user_id: string;
  scan_date: string;
  provider_name: string | null;
  document_id: string | null;
  total_body_fat_percent: number | null;
  total_lean_mass_lbs: number | null;
  total_fat_mass_lbs: number | null;
  total_bmc_lbs: number | null;
  visceral_fat_area: number | null;
  android_gynoid_ratio: number | null;
  notes: string | null;
  created_at: string;
}

// ── Epigenetics Types ──

export interface EpigeneticTest {
  id: string;
  user_id: string;
  test_date: string;
  provider_name: string | null;
  document_id: string | null;
  biological_age: number | null;
  chronological_age: number | null;
  pace_of_aging_score: number | null;
  telomere_length: number | null;
  immune_age: number | null;
  methylation_clock: string | null;
  notes: string | null;
  created_at: string;
}

// ── Fitness Types ──

export interface LiftingSession {
  id: string;
  user_id: string;
  session_date: string;
  name: string | null;
  duration_minutes: number | null;
  notes: string | null;
  sets: LiftingSet[];
  created_at: string;
}

export interface LiftingSet {
  id: string;
  session_id: string;
  exercise_name: string;
  set_number: number;
  weight_lbs: number | null;
  reps: number | null;
  rpe: number | null;
  is_warmup: boolean;
}

// ── Tracking Types ──

export interface Supplement {
  id: string;
  user_id: string;
  name: string;
  brand: string | null;
  dose_amount: string | null;
  dose_unit: string | null;
  frequency: string | null;
  is_active: boolean;
  start_date: string | null;
  end_date: string | null;
  notes: string | null;
  created_at: string;
}

export interface SupplementLog {
  id: string;
  supplement_id: string;
  taken_at: string;
  notes: string | null;
}

export interface MoodJournal {
  id: string;
  user_id: string;
  date: string;
  mood_score: number | null;
  energy_score: number | null;
  stress_score: number | null;
  notes: string | null;
  created_at: string;
}

export interface Measurement {
  id: string;
  user_id: string;
  date: string;
  metric: MeasurementMetric;
  value: number;
  unit: string | null;
  notes: string | null;
  created_at: string;
}

export interface MenstrualCycle {
  id: string;
  user_id: string;
  date: string;
  phase: MenstrualPhase;
  flow_intensity: number | null;
  symptoms: string | null;
  notes: string | null;
  created_at: string;
}

export interface DoctorVisit {
  id: string;
  user_id: string;
  visit_date: string;
  provider_name: string | null;
  specialty: string | null;
  notes: string | null;
  linked_panel_ids: string[];
  created_at: string;
}

export interface NutritionLog {
  id: string;
  user_id: string;
  date: string;
  meal_type: MealType;
  calories: number | null;
  protein_g: number | null;
  carbs_g: number | null;
  fat_g: number | null;
  fiber_g: number | null;
  notes: string | null;
  created_at: string;
}

export interface CustomMetric {
  id: string;
  user_id: string;
  name: string;
  unit: string | null;
  data_type: "numeric" | "boolean" | "text" | "scale_1_5";
  description: string | null;
  created_at: string;
}

export interface CustomMetricEntry {
  id: string;
  metric_id: string;
  date: string;
  numeric_value: number | null;
  boolean_value: boolean | null;
  text_value: string | null;
  created_at: string;
}

export interface Photo {
  id: string;
  user_id: string;
  date: string;
  photo_type: string;
  s3_key: string;
  url: string | null;
  notes: string | null;
  created_at: string;
}

// ── Goals & Insights Types ──

export interface Goal {
  id: string;
  user_id: string;
  name: string;
  metric_type: GoalMetricType;
  metric_identifier: string;
  direction: GoalDirection;
  target_value: number;
  current_value: number | null;
  unit: string | null;
  alert_threshold: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface GoalAlert {
  id: string;
  goal_id: string;
  triggered_at: string;
  message: string;
  acknowledged_at: string | null;
}

export interface Insight {
  id: string;
  user_id: string;
  insight_type: InsightType;
  title: string;
  body: string;
  confidence: number | null;
  data_points: number | null;
  domains: string[];
  is_dismissed: boolean;
  created_at: string;
}

// ── Document Types ──

export interface Document {
  id: string;
  user_id: string;
  document_type: DocumentType;
  original_filename: string;
  s3_key: string;
  file_size_bytes: number;
  mime_type: string;
  provider_name: string | null;
  parse_status: ParseStatus;
  parse_result: Record<string, unknown> | null;
  linked_record_id: string | null;
  created_at: string;
  updated_at: string;
}

// ── API Response Types ──

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
}

export interface ApiError {
  detail: string;
  status_code: number;
}

// ── Dashboard Types ──

export interface MetricSnapshot {
  label: string;
  value: string | number;
  unit: string;
  status: HealthStatus;
  trend: "up" | "down" | "flat";
  delta: string;
  sparklineData?: number[];
}
