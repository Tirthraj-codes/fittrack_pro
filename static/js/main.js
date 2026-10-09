document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.alert-dismissible').forEach(function (alertBox) {
    setTimeout(function () {
      bootstrap.Alert.getOrCreateInstance(alertBox).close();
    }, 5000);
  });
});