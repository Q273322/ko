document.addEventListener('DOMContentLoaded', function() {
    const loginForm = document.getElementById('loginForm');
    const signupForm = document.getElementById('signupForm');

    // Simulated user database
    const users = [];
    let verificationCode = "123456"; // Simulated verification code for email verification

    // Handle login
    window.submitLogin = function() {
        const email = loginForm.querySelector('input[type="email"]').value;
        const password = loginForm.querySelector('input[type="password"]').value;

        const user = users.find(user => user.email === email && user.password === password);
        if (user) {
            alert('Login successful!');
            window.location.href = 'home.html'; // Redirect to home page
        } else {
            alert('Invalid email or password. Please try again.');
        }
    };

    // Handle signup
    window.submitSignup = function() {
        const email = signupForm.querySelector('input[type="email"]').value;
        const password = signupForm.querySelector('input[type="password"]').value;

        if (users.find(user => user.email === email)) {
            alert('Email already exists. Please use a different email.');
        } else {
            users.push({ email, password });
            sendVerificationEmail(email); // Send verification email
            alert('Signup successful! Please verify your email to log in.');
        }
    };

    // Simulated email verification function
    window.sendVerificationEmail = function(email) {
        alert(`Verification email sent to ${email}. Please check your inbox.`);
    };

    // Handle verification code submission
    window.verifyEmail = function() {
        const codeInput = prompt("Enter the verification code sent to your email:");
        if (codeInput === verificationCode) {
            alert('Email verified successfully!');
            window.location.href = 'home.html'; // Redirect to home page
        } else {
            alert('Invalid verification code. Please try again.');
        }
    };
});
