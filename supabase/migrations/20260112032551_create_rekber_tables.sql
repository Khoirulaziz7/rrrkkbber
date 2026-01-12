/*
  # Rekber Bot Database Schema

  1. New Tables
    - `users`
      - `id` (bigint, primary key) - Telegram user ID
      - `username` (text) - Telegram username
      - `full_name` (text) - User's full name
      - `is_banned` (boolean) - Ban status
      - `is_admin` (boolean) - Admin status
      - `join_date` (timestamptz) - When user started bot
      - `last_active` (timestamptz) - Last interaction
      
    - `payment_methods`
      - `id` (uuid, primary key)
      - `type` (text) - 'bank' or 'ewallet'
      - `name` (text) - e.g., 'BCA', 'Dana'
      - `account_number` (text)
      - `account_name` (text)
      - `is_active` (boolean)
      - `created_at` (timestamptz)
      
    - `transactions`
      - `id` (uuid, primary key)
      - `tx_code` (text, unique) - Transaction code (RKB...)
      - `buyer_id` (bigint) - References users
      - `seller_id` (bigint) - References users
      - `buyer_username` (text)
      - `seller_username` (text)
      - `item_description` (text)
      - `price` (text)
      - `reference` (text)
      - `status` (text) - pending, approved, paid, delivered, completed, rejected, cancelled
      - `proof_url` (text) - Payment proof file
      - `notes` (text)
      - `created_at` (timestamptz)
      - `updated_at` (timestamptz)
      
    - `transaction_logs`
      - `id` (uuid, primary key)
      - `transaction_id` (uuid) - References transactions
      - `action` (text) - Status change action
      - `actor_id` (bigint) - Who performed action
      - `notes` (text)
      - `created_at` (timestamptz)

  2. Security
    - Enable RLS on all tables
    - Service role for bot operations
*/

-- Users table
CREATE TABLE IF NOT EXISTS users (
  id bigint PRIMARY KEY,
  username text,
  full_name text,
  is_banned boolean DEFAULT false,
  is_admin boolean DEFAULT false,
  join_date timestamptz DEFAULT now(),
  last_active timestamptz DEFAULT now()
);

ALTER TABLE users ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access on users"
  ON users
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- Payment methods table
CREATE TABLE IF NOT EXISTS payment_methods (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  type text NOT NULL CHECK (type IN ('bank', 'ewallet')),
  name text NOT NULL,
  account_number text NOT NULL,
  account_name text NOT NULL,
  is_active boolean DEFAULT true,
  created_at timestamptz DEFAULT now()
);

ALTER TABLE payment_methods ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access on payment_methods"
  ON payment_methods
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- Transactions table
CREATE TABLE IF NOT EXISTS transactions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tx_code text UNIQUE NOT NULL,
  buyer_id bigint REFERENCES users(id),
  seller_id bigint,
  buyer_username text,
  seller_username text,
  item_description text,
  price text,
  reference text,
  status text DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'paid', 'delivered', 'completed', 'rejected', 'cancelled')),
  proof_url text,
  notes text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access on transactions"
  ON transactions
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- Transaction logs table
CREATE TABLE IF NOT EXISTS transaction_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  transaction_id uuid REFERENCES transactions(id) ON DELETE CASCADE,
  action text NOT NULL,
  actor_id bigint,
  notes text,
  created_at timestamptz DEFAULT now()
);

ALTER TABLE transaction_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access on transaction_logs"
  ON transaction_logs
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_transactions_buyer ON transactions(buyer_id);
CREATE INDEX IF NOT EXISTS idx_transactions_seller ON transactions(seller_id);
CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status);
CREATE INDEX IF NOT EXISTS idx_transactions_created ON transactions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_transaction_logs_tx ON transaction_logs(transaction_id);
