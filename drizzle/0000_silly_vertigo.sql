CREATE TABLE `audit` (
	`id` text PRIMARY KEY NOT NULL,
	`record_id` text NOT NULL,
	`at` text NOT NULL,
	`before` text,
	`after` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `records` (
	`id` text PRIMARY KEY NOT NULL,
	`data` text NOT NULL,
	`revision` integer DEFAULT 1 NOT NULL
);
