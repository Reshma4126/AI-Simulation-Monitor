-- Database Migration: 001_initial_schema
-- Created for AI Simulation Monitor
-- Safe, idempotent execution for fresh databases.

CREATE TABLE IF NOT EXISTS `users` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `username` VARCHAR(255) NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `role` VARCHAR(50) NOT NULL,
  `created_at` DATETIME NOT NULL,
  CONSTRAINT `uq_users_username` UNIQUE (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `scenarios` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `name` VARCHAR(255) NOT NULL,
  `patient_details` JSON NOT NULL,
  `symptoms` JSON NOT NULL,
  `initial_readings` JSON NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `sessions` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `session_code` VARCHAR(50) NOT NULL,
  `created_by` INT NOT NULL,
  `started_at` DATETIME NOT NULL,
  `ended_at` DATETIME DEFAULT NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `event_log` JSON DEFAULT NULL,
  `history` JSON DEFAULT NULL,
  `current_scenario_id` INT DEFAULT NULL,
  CONSTRAINT `uq_sessions_session_code` UNIQUE (`session_code`),
  KEY `idx_sessions_created_by` (`created_by`),
  KEY `idx_sessions_current_scenario_id` (`current_scenario_id`),
  CONSTRAINT `fk_sessions_created_by` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_sessions_current_scenario_id` FOREIGN KEY (`current_scenario_id`) REFERENCES `scenarios` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `monitor_state` (
  `session_id` INT PRIMARY KEY,
  `state_data` JSON DEFAULT NULL,
  CONSTRAINT `fk_monitor_state_session_id` FOREIGN KEY (`session_id`) REFERENCES `sessions` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `debrief_reports` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `session_id` INT DEFAULT NULL,
  `session_code` VARCHAR(50) NOT NULL,
  `status` VARCHAR(50) NOT NULL DEFAULT 'COMPLETED',
  `overall_score` FLOAT DEFAULT NULL,
  `grade` VARCHAR(10) DEFAULT NULL,
  `debrief_data` JSON DEFAULT NULL,
  `pdf_path` VARCHAR(500) DEFAULT NULL,
  `error_message` TEXT DEFAULT NULL,
  `created_at` DATETIME NOT NULL,
  `updated_at` DATETIME NOT NULL,
  CONSTRAINT `uq_debrief_reports_session_id` UNIQUE (`session_id`),
  CONSTRAINT `uq_debrief_reports_session_code` UNIQUE (`session_code`),
  CONSTRAINT `fk_debrief_reports_session_id` FOREIGN KEY (`session_id`) REFERENCES `sessions` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
