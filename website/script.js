document.getElementById('scanBtn').addEventListener('click', function() {
    const pair = document.getElementById('pair').value;

fetch(`/analyze?symbol=${pair}&timeframe=20m`)

        .then(response => response.json())
        .then(data => {
            if (data.error) {
                document.getElementById('signalsTable').innerText = 'Error fetching signals. Please try again later.';

                document.getElementById('finalDecision').innerText = '';
            } else {
                const signalData = data; // Updated to match new response structure
                const signals = signalData.signal || 'No signals available'; // Extracting the signal

                const takeProfit = signalData.take_profit; // Extracting take profit
                const stopLoss = signalData.stop_loss; // Extracting stop loss

                const signalsTable = `
                    <table>
                        <tr>
                            <th>Signal Type</th>
                            <th>Signal Value</th>
                        </tr>
                        <tr>
                            <td>Signal</td>
                            <td>${signals}</td>
                        </tr>
                        <tr>
                            <td>Take Profit</td>
                            <td>${takeProfit}</td>
                        </tr>
                        <tr>
                            <td>Stop Loss</td>
                            <td>${stopLoss}</td>
                        </tr>
                        ${Object.entries(signalData).map(([key, value]) => `

                            <tr>
                                <td>${key}</td>
                                <td>${value}</td>
                            </tr>
                        `).join('')}
                    </table>
                `;
                document.getElementById('signalsTable').innerHTML = signalsTable || '<tr><td>No signals to display</td></tr>';

                document.getElementById('finalDecision').innerText = `Final Decision: ${data.final_decision || 'No Decision'}`;
            }
        })
        .catch(error => {
            document.getElementById('signalsTable').innerText = 'Error fetching signals';
            document.getElementById('finalDecision').innerText = '';
        });
    })
function toggleMenu() {
    const menu = document.getElementById("sideMenu");
    menu.style.left = (menu.style.left === "0px") ? "-250px" : "0px";
}