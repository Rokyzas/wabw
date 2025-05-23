// Render category chart function
function renderCategoryChart(categories) {
    if (!categories || Object.keys(categories).length === 0) {
        document.querySelector('.category-chart-container').innerHTML = 
            '<div class="empty-state">No category data available for chart</div>';
        return;
    }
    
    const canvas = document.getElementById('category-success-chart');
    if (!canvas) {
        console.error('Category chart canvas not found');
        return;
    }
    
    const ctx = canvas.getContext('2d');
    if (!ctx) {
        console.error('Could not get 2D context for category chart');
        return;
    }
    
    // Prepare data for chart
    const labels = Object.keys(categories);
    const successRates = Object.values(categories).map(c => c.success_rate * 100);
    
    // Generate background colors based on success rate
    const backgroundColors = successRates.map(rate => {
        if (rate >= 80) return 'rgba(46, 204, 113, 0.6)'; // Green for high success
        if (rate >= 50) return 'rgba(241, 196, 15, 0.6)'; // Yellow for medium success
        return 'rgba(231, 76, 60, 0.6)'; // Red for low success
    });
    
    // Generate border colors based on success rate
    const borderColors = successRates.map(rate => {
        if (rate >= 80) return 'rgba(39, 174, 96, 1)';
        if (rate >= 50) return 'rgba(243, 156, 18, 1)';
        return 'rgba(192, 57, 43, 1)';
    });
    
    // Destroy previous chart if exists
    if (window.categoryChart) {
        window.categoryChart.destroy();
    }
    
    try {
        // Create new chart
        window.categoryChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Success Rate (%)',
                    data: successRates,
                    backgroundColor: backgroundColors,
                    borderColor: borderColors,
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        title: {
                            display: true,
                            text: 'Success Rate (%)',
                            font: {
                                weight: 'bold'
                            }
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Category',
                            font: {
                                weight: 'bold'
                            }
                        }
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: 'Success Rate by Category',
                        font: {
                            size: 16,
                            weight: 'bold'
                        }
                    },
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            afterLabel: function(context) {
                                const idx = context.dataIndex;
                                const category = labels[idx];
                                const stats = categories[category];
                                return [
                                    `Tasks: ${stats.total_tasks || 0}`,
                                    `Completed: ${stats.completed_tasks || 0}`,
                                    `Failed: ${stats.failed_tasks || 0}`,
                                    `Avg. Duration: ${stats.avg_duration ? stats.avg_duration.toFixed(1) + 's' : '0s'}`,
                                    `Avg. Actions: ${stats.avg_actions ? stats.avg_actions.toFixed(1) : '0'}`
                                ];
                            }
                        }
                    }
                }
            }
        });
    } catch (err) {
        console.error('Error creating category chart:', err);
        document.querySelector('.category-chart-container').innerHTML = 
            '<div class="error-state">Error creating chart: ' + err.message + '</div>';
    }
}
