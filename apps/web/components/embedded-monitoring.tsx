"use client";

import { createContext } from "react";

// Native editors retain their own state and permissions inside the settings hub.
export const EmbeddedMonitoring = createContext(false);
