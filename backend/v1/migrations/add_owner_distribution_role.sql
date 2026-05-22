-- Migration: add owner_distribution to role_enum
-- Run in Supabase SQL editor before deploying classifier changes.
-- Safe to run multiple times (IF NOT EXISTS guard).
ALTER TYPE role_enum ADD VALUE IF NOT EXISTS 'owner_distribution';
