package com.yojnasetu.error;

import java.util.List;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.ProblemDetail;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.context.request.WebRequest;
import org.springframework.web.method.annotation.HandlerMethodValidationException;
import org.springframework.web.servlet.mvc.method.annotation.ResponseEntityExceptionHandler;

/**
 * Every error leaves as an RFC 9457 problem detail. Validation problems name the invalid fields;
 * anything unexpected is logged here and answered with a generic message (no stack traces or internals).
 */
@RestControllerAdvice
class ApiExceptionHandler extends ResponseEntityExceptionHandler {

	private static final Logger log = LoggerFactory.getLogger(ApiExceptionHandler.class);

	@Override
	protected ResponseEntity<Object> handleMethodArgumentNotValid(MethodArgumentNotValidException ex,
			HttpHeaders headers, HttpStatusCode status, WebRequest request) {
		List<String> errors = ex.getBindingResult().getFieldErrors().stream()
			.map(e -> e.getField() + ": " + e.getDefaultMessage())
			.toList();
		return ResponseEntity.badRequest().body(invalid(errors));
	}

	@Override
	protected ResponseEntity<Object> handleHandlerMethodValidationException(HandlerMethodValidationException ex,
			HttpHeaders headers, HttpStatusCode status, WebRequest request) {
		List<String> errors = ex.getParameterValidationResults().stream()
			.flatMap(result -> result.getResolvableErrors().stream()
				.map(e -> (e instanceof FieldError f ? f.getField() : result.getMethodParameter().getParameterName())
						+ ": " + e.getDefaultMessage()))
			.toList();
		return ResponseEntity.badRequest().body(invalid(errors));
	}

	@ExceptionHandler(DataAccessResourceFailureException.class)
	ProblemDetail databaseUnavailable(DataAccessResourceFailureException ex) {
		log.error("Database unreachable", ex);
		return ProblemDetail.forStatusAndDetail(HttpStatus.SERVICE_UNAVAILABLE,
				"Scheme data is temporarily unavailable. Please try again shortly.");
	}

	@ExceptionHandler(Exception.class)
	ProblemDetail unexpected(Exception ex) {
		log.error("Unhandled error", ex);
		return ProblemDetail.forStatusAndDetail(HttpStatus.INTERNAL_SERVER_ERROR,
				"Something went wrong on our side. Please try again.");
	}

	private static ProblemDetail invalid(List<String> errors) {
		ProblemDetail problem = ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST,
				"Some of the information provided is not valid.");
		problem.setProperty("errors", errors);
		return problem;
	}

}
