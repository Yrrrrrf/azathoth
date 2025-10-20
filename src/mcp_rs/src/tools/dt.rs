//! A module for working with dates, times, and timestamps.
//!
//! This module provides structs and methods for representing and manipulating dates and times.
//! It includes support for creating dates and times, converting between timestamps and datetime objects,
//! and parsing datetime strings.
//!
//! # Features
//! - [Date], [Time], and [DateTime] structs for representing date and time components
//! - Methods for creating and validating date and time objects
//! - Conversion between timestamps and [DateTime] objects
//! - Parsing of datetime strings
//! - Error handling for invalid dates, times, and parsing errors
//!
//! # Examples
//! ```
//! use dev_utils::datetime::{Date, Time, DateTime};
//! use std::str::FromStr;
//!
//! let date = Date::new(2023, 5, 1).unwrap();
//! let time = Time::new(12, 34, 56).unwrap();
//! let dt = DateTime { date, time };
//!
//! assert_eq!(dt.to_string(), "2023-05-01 12:34:56");
//!
//! let parsed_dt = DateTime::from_str("2023-05-01 12:34:56").unwrap();
//! assert_eq!(parsed_dt, dt);
//! ```
use std::error::Error;
use std::fmt::{self};
use std::str::FromStr;
use std::time::{SystemTime, UNIX_EPOCH};

/// Represents a date with year, month, and day.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub struct Date {
    year: i32,
    month: u8,
    day: u8,
}

// Represents a time with hour, minute, and second.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub struct Time {
    hour: u8,
    minute: u8,
    second: u8,
}

/// Represents a combination of date and time.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub struct DateTime {
    pub date: Date,
    pub time: Time,
}

/// Represents errors that can occur when working with dates and times.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DateTimeError {
    InvalidYear(i32),
    InvalidMonth(u8),
    InvalidDay(u8),
    InvalidHour(u8),
    InvalidMinute(u8),
    InvalidSecond(u8),
    InvalidDate { year: i32, month: u8, day: u8 },
    InvalidTime { hour: u8, minute: u8, second: u8 },
    ParseError(String),
}

impl fmt::Display for DateTimeError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidYear(year) => write!(f, "Invalid year: {}", year),
            Self::InvalidMonth(month) => write!(f, "Invalid month: {}", month),
            Self::InvalidDay(day) => write!(f, "Invalid day: {}", day),
            Self::InvalidHour(hour) => write!(f, "Invalid hour: {}", hour),
            Self::InvalidMinute(minute) => write!(f, "Invalid minute: {}", minute),
            Self::InvalidSecond(second) => write!(f, "Invalid second: {}", second),
            Self::InvalidDate { year, month, day } => {
                write!(f, "Invalid date: {}-{}-{}", year, month, day)
            }
            Self::InvalidTime {
                hour,
                minute,
                second,
            } => write!(f, "Invalid time: {}:{}:{}", hour, minute, second),
            Self::ParseError(msg) => write!(f, "Parse error: {}", msg),
        }
    }
}

impl Error for DateTimeError {}

impl Date {
    /// Creates a new [Date] instance.
    ///
    /// # Arguments
    /// * `year` - The year (can be negative for BCE dates)
    /// * `month` - The month (1-12)
    /// * `day` - The day of the month (1-31, depending on the month and year)
    ///
    /// # Returns
    /// A `Result` containing either the valid [Date] or a [DateTimeError].
    ///
    /// # Examples
    ///
    /// ```
    /// use dev_utils::datetime::Date;
    ///
    /// let date = Date::new(2023, 5, 1).unwrap();
    /// assert!(Date::new(2023, 2, 29).is_err()); // Not a leap year
    /// ```
    pub const fn new(year: i32, month: u8, day: u8) -> Result<Self, DateTimeError> {
        match (month, day) {
            (m, d) if m >= 1 && m <= 12 && d >= 1 && d <= Self::days_in_month(year, m) => {
                Ok(Self {
                    year,
                    month: m,
                    day: d,
                })
            }
            (m, _) if m < 1 || m > 12 => Err(DateTimeError::InvalidMonth(m)),
            (_, d) => Err(DateTimeError::InvalidDay(d)),
        }
    }

    /// Calculates the number of days in a given month of a specific year.
    ///
    /// # Arguments
    /// * `year` - The year
    /// * `month` - The month (1-12)
    ///
    /// # Returns
    /// The number of days in the specified month.
    ///
    /// # Examples
    /// ```
    /// use dev_utils::datetime::Date;
    ///
    /// assert_eq!(Date::days_in_month(2023, 2), 28);
    /// assert_eq!(Date::days_in_month(2024, 2), 29); // Leap year
    /// ```
    pub const fn days_in_month(year: i32, month: u8) -> u8 {
        const DAYS: [u8; 12] = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
        DAYS[month as usize - 1] + ((month == 2 && Self::is_leap_year(year)) as u8)
    }

    /// Determines if a given year is a leap year.
    ///
    /// # Arguments
    /// * `year` - The year to check
    ///
    /// # Returns
    /// `true` if the year is a leap year, `false` otherwise.
    ///
    /// # Examples
    /// ```
    /// use dev_utils::datetime::Date;
    ///
    /// assert!(!Date::is_leap_year(2023));
    /// assert!(Date::is_leap_year(2024));
    /// ```
    pub const fn is_leap_year(year: i32) -> bool {
        year % 4 == 0 && (year % 100 != 0 || year % 400 == 0)
    }
}

impl fmt::Display for Date {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{:04}-{:02}-{:02}", self.year, self.month, self.day)
    }
}

impl Time {
    /// Creates a new [Time] instance.
    ///
    /// # Arguments
    /// * `hour` - The hour (0-23)
    /// * `minute` - The minute (0-59)
    /// * `second` - The second (0-59)
    ///
    /// # Returns
    /// A `Result` containing either the valid [Time] or a [DateTimeError].
    ///
    /// # Examples
    /// ```
    /// use dev_utils::datetime::Time;
    ///
    /// let time = Time::new(12, 34, 56).unwrap();
    /// assert!(Time::new(24, 0, 0).is_err());
    /// ```
    pub const fn new(hour: u8, minute: u8, second: u8) -> Result<Self, DateTimeError> {
        match (hour, minute, second) {
            (h, m, s) if h < 24 && m < 60 && s < 60 => Ok(Self {
                hour: h,
                minute: m,
                second: s,
            }),
            (h, _, _) if h >= 24 => Err(DateTimeError::InvalidHour(h)),
            (_, m, _) if m >= 60 => Err(DateTimeError::InvalidMinute(m)),
            (_, _, s) if s >= 60 => Err(DateTimeError::InvalidSecond(s)),
            _ => unreachable!(), // * This case should never happen due to the nature of u8
        }
    }
}

impl fmt::Display for Time {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{:02}:{:02}:{:02}", self.hour, self.minute, self.second)
    }
}

impl DateTime {
    /// Returns a [DateTime] instance representing the current date and time.
    ///
    /// # Examples
    /// ```
    /// use dev_utils::datetime::DateTime;
    ///
    /// let now = DateTime::now();
    /// println!("Current date and time: {}", now);
    /// ```
    pub fn now() -> Self {
        let now = SystemTime::now().duration_since(UNIX_EPOCH).unwrap();
        Self::from_timestamp(now.as_secs() as i64).unwrap()
    }

    /// Creates a [DateTime] instance from a Unix timestamp.
    ///
    /// # Arguments
    /// * `timestamp` - The Unix timestamp (seconds since 1970-01-01 00:00:00 UTC)
    ///
    /// # Returns
    /// A `Result` containing either the valid `DateTime` or a `DateTimeError`.
    ///
    /// # Examples
    /// ```
    /// use dev_utils::datetime::DateTime;
    ///
    /// let dt = DateTime::from_timestamp(1682899200).unwrap();
    /// assert_eq!(dt.to_string(), "2023-05-02 00:00:00");
    /// ```
    pub fn from_timestamp(timestamp: i64) -> Result<Self, DateTimeError> {
        let (days, seconds) = (timestamp / 86400, timestamp % 86400);
        let (year, month, day) = Self::calculate_ymd(days);
        let (hour, minute, second) = (seconds / 3600, (seconds % 3600) / 60, seconds % 60);

        Ok(Self {
            date: Date::new(year, month, day + 1)?,
            time: Time::new(hour as u8, minute as u8, second as u8)?,
        })
    }

    /// Calculates the year, month, and day from the number of days since 1970-01-01.
    ///
    /// # Arguments
    /// * `days` - The number of days since 1970-01-01
    ///
    /// # Returns
    /// A tuple containing the calculated (year, month, day).
    fn calculate_ymd(mut days: i64) -> (i32, u8, u8) {
        let mut year = 1970;
        let mut month = 1;

        while days >= 365 + Date::is_leap_year(year) as i64 {
            days -= 365 + Date::is_leap_year(year) as i64;
            year += 1;
        }

        while days >= Date::days_in_month(year, month) as i64 {
            days -= Date::days_in_month(year, month) as i64;
            month += 1;
        }

        (year, month, days as u8 + 1)
    }
}

impl fmt::Display for DateTime {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "{:04}-{:02}-{:02} {:02}:{:02}:{:02}", // 2023-05-01 12:34:56
            self.date.year,
            self.date.month,
            self.date.day, // date
            self.time.hour,
            self.time.minute,
            self.time.second // time
        )
    }
}

impl FromStr for DateTime {
    type Err = DateTimeError;

    /// Parses a string into a [DateTime] instance.
    ///
    /// The expected format is "YYYY-MM-DD HH:MM:SS".
    ///
    /// # Arguments
    /// * `s` - The string to parse
    ///
    /// # Returns
    /// A `Result` containing either the parsed [DateTime] or a [DateTimeError].
    ///
    /// # Examples
    /// ```
    /// use dev_utils::datetime::DateTime;
    /// use std::str::FromStr;
    ///
    /// let dt = DateTime::from_str("2023-05-01 12:34:56").unwrap();
    /// assert_eq!(dt.to_string(), "2023-05-01 12:34:56");
    /// ```
    fn from_str(s: &str) -> Result<Self, Self::Err> {
        let parts: Vec<&str> = s.split_whitespace().collect();
        if parts.len() != 2 {
            return Err(DateTimeError::ParseError("Invalid format".to_string()));
        }

        let date_parts: Vec<&str> = parts[0].split('-').collect();
        let time_parts: Vec<&str> = parts[1].split(':').collect();

        if date_parts.len() != 3 || time_parts.len() != 3 {
            return Err(DateTimeError::ParseError("Invalid format".to_string()));
        }

        fn parse_part<T>(part: &str, name: &str) -> Result<T, DateTimeError>
        where
            T: FromStr,
        {
            part.parse()
                .map_err(|_| DateTimeError::ParseError(format!("Invalid {}", name)))
        }

        let year: i32 = parse_part(date_parts[0], "year")?;
        let month: u8 = parse_part(date_parts[1], "month")?;
        let day: u8 = parse_part(date_parts[2], "day")?;
        let hour: u8 = parse_part(time_parts[0], "hour")?;
        let minute: u8 = parse_part(time_parts[1], "minute")?;
        let second: u8 = parse_part(time_parts[2], "second")?;

        Ok(Self {
            date: Date::new(year, month, day)?,
            time: Time::new(hour, minute, second)?,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_date_creation() {
        assert!(Date::new(2023, 4, 30).is_ok());
        assert!(Date::new(2023, 2, 29).is_err());
        assert!(Date::new(2024, 2, 29).is_ok());
    }

    #[test]
    fn test_time_creation() {
        assert!(Time::new(23, 59, 59).is_ok());
        assert!(Time::new(24, 0, 0).is_err());
    }

    #[test]
    fn test_datetime_from_timestamp() {
        let dt = DateTime::from_timestamp(1682899200).unwrap();
        assert_eq!(dt.to_string(), "2023-05-01 00:00:00");
    }

    #[test]
    fn test_datetime_parsing() {
        let dt: DateTime = "2023-05-01 12:34:56".parse().unwrap();
        assert_eq!(dt.to_string(), "2023-05-01 12:34:56");
    }

    #[test]
    fn test_error_display() {
        let err = DateTimeError::InvalidYear(2023);
        assert_eq!(err.to_string(), "Invalid year: 2023");
    }
}
