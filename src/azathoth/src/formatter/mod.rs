//! A module for printing formatted output.

#[derive(Debug)]
struct DataPoint {
    id: i32,
    label: String,
    value: f64,
}

/// Prints a formatted table of data points.
pub fn print_formatted_data() {
    let data = vec![
        DataPoint {
            id: 1,
            label: "Alpha".to_string(),
            value: 12.345,
        },
        DataPoint {
            id: 2,
            label: "Beta".to_string(),
            value: 67.89,
        },
        DataPoint {
            id: 10,
            label: "Gamma".to_string(),
            value: 1.0,
        },
    ];

    println!("--- Formatted Data Points ---");
    println!("{:<5} | {:<10} | {:>10}", "ID", "Label", "Value");
    println!("{:-<5} | {:-<10} | {:->10}", "", "", "");

    for point in data {
        println!(
            "{:<5} | {:<10} | {:>10.3}",
            point.id, point.label, point.value
        );
    }
    println!("-----------------------------");
}
