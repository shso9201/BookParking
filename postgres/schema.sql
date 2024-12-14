CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,                -- Auto-incrementing ID
    lot_id TEXT NOT NULL,                  -- Lot ID (integer)
    date DATE NOT NULL,                   -- Date of the transaction
    start_time TIME NOT NULL,             -- Start time (HH:MM format)
    end_time TIME NOT NULL,               -- End time (HH:MM format)
    phone TEXT NOT NULL,           -- Phone number (string, 15 characters max)
    state TEXT NOT NULL,            -- State (string, 2 characters for US state)
    license_plate TEXT NOT NULL,   -- License plate (string, 20 characters max)
    card_number TEXT,              -- Card number (string, 20 characters max, optional)
    filename TEXT,         -- URL of the license photo, now unique
    results TEXT,                         -- Result form Openalpr
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP -- Timestamp of record creation
);