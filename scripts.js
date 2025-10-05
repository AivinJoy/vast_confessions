 // --- IMPORTANT: Replace with your actual Supabase URL and Anon Key ---
const SUPABASE_URL = 'https://bhpwnbegsfzijzievdwd.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJocHduYmVnc2Z6aWp6aWV2ZHdkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTg1NTU0MDQsImV4cCI6MjA3NDEzMTQwNH0.84KONXKHvh8X2_kCVADlNND8g6Wx_0Q63l6yK2M8Dv8';
    
const supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
const loginForm = document.getElementById('admin-login-form');
const errorMessage = document.getElementById('error-message');
loginForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    errorMessage.textContent = ''; // Clear previous errors
    const email = document.getElementById('admin-email').value;
    const password = document.getElementById('admin-password').value;
    const rememberMe = document.getElementById('remember-me').checked;
    console.log('Attempting to log in with email:', email); // Debugging line
    console.log('Remember me selected:', rememberMe);
    const { data, error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) {
        // If there's an error, this block runs
        console.error('Login failed:', error); // See the detailed error in the console
        errorMessage.textContent = error.message;
    } else {
        // If login is successful, this block runs
        console.log('Login successful! User data:', data); // See the user data
        console.log("Redirecting to index.html...");
        window.location.href = 'index.html'; 
    }
});
