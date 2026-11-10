import { sqliteTable, text, integer } from 'drizzle-orm/sqlite-core';
export const records = sqliteTable('records', { id: text('id').primaryKey(), data: text('data').notNull(), revision: integer('revision').notNull().default(1) });
export const audit = sqliteTable('audit', { id: text('id').primaryKey(), recordId: text('record_id').notNull(), at: text('at').notNull(), before: text('before'), after: text('after').notNull() });
