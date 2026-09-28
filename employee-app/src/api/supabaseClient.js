import { createClient } from "@supabase/supabase-js";

const supabaseUrl = "https://zvogktuqdcpjsfargewg.supabase.co";
const supabaseKey = "sb_publishable_nxCLI2Lj9Io__yHL2gxtTg_ybbfGWD4";

export const supabase = createClient(supabaseUrl, supabaseKey);
